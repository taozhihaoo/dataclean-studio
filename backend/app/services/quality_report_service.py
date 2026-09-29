"""Data quality report: summary + per-column statistics for a job."""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool

from app.core.dataframe_ops.merge import count_null_cells
from app.core.dataframe_ops.profile import (
    count_exact_duplicates,
    count_invalid_dates,
    count_invalid_emails,
    count_nulls,
    profile_dataframe,
)
from app.core.utils import utc_now_iso
from app.db import repositories
from app.services import dataset_store
from app.services.job_service import get_job_or_error


async def build_report(job_id: str) -> dict[str, Any]:
    return await run_in_threadpool(_build_sync, job_id)


def _build_sync(job_id: str) -> dict[str, Any]:
    job = get_job_or_error(job_id)
    df = dataset_store.load_current(job_id)

    report: dict[str, Any] = {
        "job_id": job_id,
        "filename": job["filename"],
        "generated_at": utc_now_iso(),
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "null_counts": count_nulls(df),
        "null_cells_total": count_null_cells(df),
        "duplicate_rows": count_exact_duplicates(df),
        "invalid_email_count": count_invalid_emails(df),
        "invalid_date_count": count_invalid_dates(df),
        "columns": profile_dataframe(df),
    }

    original = dataset_store.load_original(job_id)
    report["original_rows"] = int(len(original))
    report["rows_delta"] = int(len(df)) - int(len(original))

    report["validation"] = _last_run_summary(job_id, "validate")
    report["transform"] = _last_run_summary(job_id, "transform")
    report["merge"] = _last_run_summary(job_id, "merge")
    return report


def _last_run_summary(job_id: str, kind: str) -> dict[str, Any] | None:
    runs = repositories.list_runs(job_id, kind=kind)
    if not runs:
        return None
    latest = runs[0]
    return {
        "run_id": latest["id"],
        "at": latest["created_at"],
        "summary": latest["summary"],
    }
