"""Export the current dataset of a job to CSV / JSON / XLSX."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app.core.dataframe_ops.exporters import EXTENSIONS, MEDIA_TYPES, export_dataframe
from app.core.security import sanitize_filename
from app.db import repositories
from app.schemas.operations import ExportRequest
from app.services import dataset_store
from app.services.job_service import get_job_or_error


@dataclass
class ExportResult:
    path: Path
    media_type: str
    filename: str
    stats: dict


async def export_job(job_id: str, request: ExportRequest) -> ExportResult:
    return await run_in_threadpool(_export_sync, job_id, request)


def _export_sync(job_id: str, request: ExportRequest) -> ExportResult:
    get_job_or_error(job_id)
    df = dataset_store.load_current(job_id)

    base = sanitize_filename(request.filename or "dataclean_export")
    stem = Path(base).stem or "dataclean_export"
    filename = f"{stem}{EXTENSIONS[request.file_format]}"
    out_path = dataset_store.export_dir(job_id) / filename

    stats = export_dataframe(
        df, request.file_format, out_path, guard_formulas=request.guard_formulas
    )
    repositories.create_run(
        job_id,
        kind="export",
        status="success",
        summary={"filename": filename, **stats},
    )
    return ExportResult(
        path=out_path,
        media_type=MEDIA_TYPES[request.file_format],
        filename=filename,
        stats=stats,
    )
