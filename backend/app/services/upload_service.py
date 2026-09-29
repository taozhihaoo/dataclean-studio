"""Upload handling: size caps, content sniffing, parsing, job creation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.core.dataframe_ops import parsers
from app.core.dataframe_ops.profile import profile_dataframe
from app.core.errors import DataCleanError
from app.core.security import sanitize_filename, sniff_content_kind
from app.core.utils import new_id
from app.db import repositories
from app.services import dataset_store

logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".csv": "text", ".xlsx": "zip", ".xls": "ole2"}
_CHUNK = 1024 * 1024


@dataclass
class UploadOutcome:
    job_id: str
    filename: str
    size_bytes: int
    row_count: int
    column_count: int
    status: str


async def save_and_create_job(upload: UploadFile, settings: Settings) -> UploadOutcome:
    """Store the upload safely, parse it, and register file + job."""
    safe_name = sanitize_filename(upload.filename or "upload")
    extension = Path(safe_name).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS:
        raise DataCleanError(
            "unsupported_file_type",
            f"Unsupported file type '{extension or '(none)'}'. Supported: .csv, .xlsx, .xls",
        )

    temp_path = settings.upload_dir / f"{new_id()}.part"
    size = 0
    try:
        with temp_path.open("wb") as out:
            head = b""
            while chunk := await upload.read(_CHUNK):
                if not head:
                    head = chunk[:16]
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise DataCleanError(
                        "file_too_large",
                        f"File exceeds the {settings.max_upload_mb} MB upload limit.",
                        status_code=413,
                    )
                out.write(chunk)
        if size == 0:
            raise DataCleanError("empty_file", "The uploaded file is empty.")

        content_kind = _match_extension(head, extension, safe_name)
        # Parsing is CPU-bound pandas work: keep it off the event loop.
        return await run_in_threadpool(_finalize_upload, temp_path, safe_name, size, content_kind)
    finally:
        temp_path.unlink(missing_ok=True)


def _match_extension(head: bytes, extension: str, filename: str) -> str:
    kind = sniff_content_kind(head)
    expected = _ALLOWED_EXTENSIONS[extension]
    if kind == "binary":
        raise DataCleanError(
            "invalid_encoding",
            f"'{filename}' does not look like a text or Excel file.",
        )
    if kind != expected:
        raise DataCleanError(
            "content_type_mismatch",
            f"File content does not match the .{extension.lstrip('.')} extension"
            " (we do not trust the declared type; check the actual file).",
        )
    return kind


def _finalize_upload(
    temp_path: Path, safe_name: str, size: int, content_kind: str
) -> UploadOutcome:
    try:
        df = parsers.load_dataframe(temp_path, content_kind)
    except DataCleanError:
        raise
    except Exception as exc:  # pandas can raise a long tail of parse errors
        logger.info("Unhandled parse failure for %s: %s", safe_name, exc)
        raise DataCleanError(
            "malformed_csv" if content_kind == "text" else "malformed_xlsx",
            "The file could not be parsed. Verify that it is a valid CSV/Excel file.",
        ) from exc

    stored_path = get_upload_path(temp_path.name, safe_name)
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.replace(stored_path)

    file_record = repositories.create_file(
        original_filename=safe_name,
        stored_path=str(stored_path),
        size_bytes=size,
        content_kind=content_kind,
    )
    job = repositories.create_job(
        filename=safe_name,
        file_id=file_record["id"],
        row_count=int(len(df)),
        column_count=int(len(df.columns)),
    )
    dataset_store.save_original(job["id"], df)
    logger.info(
        "Uploaded %s -> job %s (%d rows x %d cols)",
        safe_name,
        job["id"],
        len(df),
        len(df.columns),
    )
    return UploadOutcome(
        job_id=job["id"],
        filename=safe_name,
        size_bytes=size,
        row_count=int(len(df)),
        column_count=int(len(df.columns)),
        status="ready",
    )


def get_upload_path(file_id_part: str, safe_name: str) -> Path:
    token = file_id_part.removesuffix(".part")
    return get_settings().upload_dir / f"{token}__{safe_name}"


def load_upload_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


__all__ = ["save_and_create_job", "UploadOutcome", "profile_dataframe"]
