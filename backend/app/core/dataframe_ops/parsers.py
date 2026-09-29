"""Load CSV / XLSX / XLS uploads into a canonical all-string DataFrame.

Canonical model: every cell is a ``str``; missing values are ``None``
(empty strings are the "null" of raw input and are converted to None by
explicit cleaning steps). Keeping the source representation makes cleaning
predictable: ``03/04/2025`` stays ``03/04/2025`` until the user normalizes
dates, and leading zeros survive.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path

import pandas as pd

from app.core.errors import DataCleanError

logger = logging.getLogger(__name__)

# Some real-world files contain huge single fields; raise the stdlib cap.
csv.field_size_limit(10 * 1024 * 1024)

_MAX_XLSX_CELL_RUN = 1_000_000
_MANGLED_NAME = re.compile(r"^(.*)\.(\d+)$")


def load_dataframe(path: Path, content_kind: str) -> pd.DataFrame:
    """Parse an uploaded file into the canonical string DataFrame."""
    if content_kind == "text":
        return _load_csv(path)
    if content_kind == "zip":
        return _load_excel(path, engine="openpyxl")
    if content_kind == "ole2":
        return _load_excel(path, engine="xlrd")
    raise DataCleanError(
        "unsupported_file_type",
        "Unsupported file content. Please upload a CSV or Excel file.",
    )


def _decode_text(raw: bytes) -> str:
    decoded: str | None = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise DataCleanError(
            "invalid_encoding",
            "Could not decode the file as text. Please upload a UTF-8 or CP1252 encoded CSV.",
        )
    if "\x00" in decoded:
        raise DataCleanError(
            "invalid_encoding",
            "The file contains binary data and cannot be read as a CSV.",
        )
    return decoded


def _sniff_and_validate_shape(text: str) -> str:
    """Detect the delimiter and reject ragged rows (malformed CSV).

    pandas silently pads short rows, which would hide data corruption from
    a *cleaning* tool; csv.reader does not.
    """
    sample = text[:16384]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    rows = csv.reader(io.StringIO(text), delimiter=delimiter)
    widths = {len(row) for row in rows if row}
    if len(widths) > 1:
        raise DataCleanError(
            "malformed_csv",
            f"The CSV file is malformed: rows have inconsistent field counts {sorted(widths)}.",
        )
    return delimiter


def _load_csv(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    if not raw.strip():
        raise DataCleanError("empty_file", "The file is empty.")
    text = _decode_text(raw)
    delimiter = _sniff_and_validate_shape(text)
    try:
        # dtype=str keeps every cell exactly as written; na_filter=False
        # means no silent NaN conversion.
        frame = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            engine="python",
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )
    except pd.errors.EmptyDataError as exc:
        raise DataCleanError("empty_file", "The file contains no data rows.") from exc
    except pd.errors.ParserError as exc:
        logger.info("CSV parse error: %s", exc)
        raise DataCleanError(
            "malformed_csv",
            "The CSV file is malformed (quoting or field structure is broken).",
        ) from exc
    if frame.empty and len(frame.columns) == 0:
        raise DataCleanError("empty_file", "The file contains no data rows.")
    return _normalize_columns(frame)


def _load_excel(path: Path, engine: str) -> pd.DataFrame:
    kind = "XLSX" if engine == "openpyxl" else "XLS"
    try:
        frame = pd.read_excel(io.BytesIO(path.read_bytes()), engine=engine, sheet_name=0)
    except Exception as exc:  # zipfile.BadZipFile, xlrd errors, openpyxl errors
        logger.info("Excel parse error (%s): %s", kind, exc)
        raise DataCleanError(
            f"malformed_{kind.lower()}", f"The {kind} file could not be parsed."
        ) from exc
    if frame.empty and len(frame.columns) == 0:
        raise DataCleanError("empty_file", "The first sheet contains no data rows.")
    return _normalize_columns(_stringify_excel_frame(frame))


def _stringify_excel_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert typed Excel cells into the canonical string representation."""
    converted = pd.DataFrame(index=frame.index)
    for column in frame.columns:
        series = frame[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            converted[column] = series.map(_format_timestamp)
        elif pd.api.types.is_bool_dtype(series):
            converted[column] = series.map(lambda v: "True" if v else "False")
        elif pd.api.types.is_numeric_dtype(series):
            converted[column] = series.map(_format_number)
        else:
            converted[column] = series.map(_format_cell)
    return converted


def _format_timestamp(value: pd.Timestamp) -> str:
    if pd.isna(value):
        return ""
    if (value.hour, value.minute, value.second) == (0, 0, 0):
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _format_number(value: float) -> str:
    if pd.isna(value):
        return ""
    if float(value).is_integer() and abs(value) < 1e15:
        return str(int(value))
    return str(value)


def _format_cell(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Give every column a non-empty, unique, readable string name.

    Handles pandas artifacts: duplicate headers arrive mangled ("a", "a.1")
    and blank headers arrive as "Unnamed: 0".
    """
    names: list[str] = []
    for index, column in enumerate(frame.columns):
        name = str(column).strip()
        if not name or name.lower().startswith("unnamed:"):
            name = f"column_{index + 1}"
        else:
            mangled = _MANGLED_NAME.match(name)
            if mangled and mangled.group(1):
                name = f"{mangled.group(1)}_{int(mangled.group(2)) + 1}"
        candidate, suffix = name, 2
        while candidate in names:
            candidate = f"{name}_{suffix}"
            suffix += 1
        names.append(candidate)
    frame.columns = names
    return frame.astype(object)


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """Rows as dicts with str or None values (safe for JSON)."""
    return [
        {column: _json_cell(row[column]) for column in df.columns}
        for row in df.to_dict("records")[:_MAX_XLSX_CELL_RUN]
    ]


def _json_cell(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)
