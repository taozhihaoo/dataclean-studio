"""CSV / JSON / XLSX writers with spreadsheet formula-injection protection."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from app.core.dataframe_ops.parsers import dataframe_to_records
from app.core.errors import DataCleanError
from app.core.security import is_dangerous_formula, sanitize_formula_value

logger = logging.getLogger(__name__)

MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
EXTENSIONS = {"csv": ".csv", "json": ".json", "xlsx": ".xlsx"}


def export_dataframe(
    df: pd.DataFrame, file_format: str, out_path: Path, guard_formulas: bool = True
) -> dict:
    """Write the dataset in the requested format; return export stats."""
    working = df.copy()
    sanitized_cells = 0
    if guard_formulas and file_format in ("csv", "xlsx"):
        working, sanitized_cells = _guard_formulas(working)

    if file_format == "csv":
        working.fillna("").to_csv(out_path, index=False, encoding="utf-8-sig", lineterminator="\n")
    elif file_format == "json":
        records = dataframe_to_records(df)  # JSON needs no formula guard
        out_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    elif file_format == "xlsx":
        _write_xlsx(working, out_path)
    else:
        raise DataCleanError(
            "unsupported_export_format", f"Unsupported export format '{file_format}'."
        )

    return {
        "format": file_format,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "size_bytes": out_path.stat().st_size,
        "formula_cells_sanitized": sanitized_cells,
    }


def _guard_formulas(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Prefix formula-like strings with a single quote (Excel-safe)."""
    guarded = df.copy()
    count = 0
    for column in guarded.columns:
        series = guarded[column]
        values = series.map(lambda v: sanitize_formula_value(v) if isinstance(v, str) else v)
        count += int(series.map(lambda v: isinstance(v, str) and is_dangerous_formula(v)).sum())
        guarded[column] = values
    return guarded, count


def _write_xlsx(df: pd.DataFrame, out_path: Path) -> None:
    try:
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df.fillna("").to_excel(writer, index=False, sheet_name="Data")
            sheet = writer.sheets["Data"]
            from openpyxl.styles import Font

            bold = Font(bold=True)
            for cell in sheet[1]:
                cell.font = bold
            sheet.freeze_panes = "A2"
            for index, column in enumerate(df.columns, start=1):
                width = max([len(str(column))] + [len(str(v)) for v in df[column].head(50)])
                sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = min(
                    max(width + 2, 10), 50
                )
    except OSError as exc:
        logger.exception("XLSX export failed")
        raise DataCleanError(
            "export_failure", "Could not write the Excel file.", details={"reason": str(exc)}
        ) from exc
