"""Job queries, detail assembly, preview, and deletion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.dataframe_ops import parsers
from app.core.dataframe_ops.profile import profile_dataframe
from app.core.errors import DataCleanError
from app.db import repositories
from app.services import dataset_store


def get_job_or_error(job_id: str) -> dict[str, Any]:
    job = repositories.get_job(job_id)
    if not job:
        raise DataCleanError("job_not_found", f"Job '{job_id}' was not found.", status_code=404)
    return job


def job_detail(job: dict[str, Any]) -> dict[str, Any]:
    df = dataset_store.load_current(job["id"])
    size_bytes = None
    if job.get("file_id"):
        file_record = repositories.get_file(job["file_id"])
        if file_record:
            size_bytes = file_record["size_bytes"]
    return {
        "job_id": job["id"],
        "filename": job["filename"],
        "source": job["source"],
        "status": job["status"],
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "size_bytes": size_bytes,
        "is_transformed": job["status"] == "transformed",
        "columns": profile_dataframe(df),
    }


def job_preview(job: dict[str, Any], limit: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    limit = min(limit or settings.preview_row_limit, settings.max_preview_rows)
    df = dataset_store.load_current(job["id"])
    rows = parsers.dataframe_to_records(df.head(limit))
    return {
        "columns": [str(c) for c in df.columns],
        "rows": rows,
        "total_rows": int(len(df)),
        "limited": len(df) > limit,
    }


def delete_job(job_id: str) -> None:
    get_job_or_error(job_id)
    file_id = repositories.delete_job(job_id)
    dataset_store.delete_workspace(job_id)
    dataset_store.delete_exports(job_id)
    if file_id:
        file_record = repositories.delete_file(file_id)
        if file_record:
            stored = Path(file_record["stored_path"])
            if stored.exists() and stored.parent == get_settings().upload_dir.resolve():
                stored.unlink(missing_ok=True)


__all__ = [
    "get_job_or_error",
    "job_detail",
    "job_preview",
    "delete_job",
    "profile_dataframe",
]
