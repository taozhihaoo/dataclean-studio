"""Merge multiple job datasets into a new job."""

from __future__ import annotations

import logging

from starlette.concurrency import run_in_threadpool

from app.core.dataframe_ops.merge import merge_frames
from app.core.errors import DataCleanError
from app.db import repositories
from app.schemas.operations import MergeRequest, MergeResponse
from app.services import dataset_store
from app.services.job_service import get_job_or_error

logger = logging.getLogger(__name__)


async def merge(request: MergeRequest) -> MergeResponse:
    return await run_in_threadpool(_merge_sync, request)


def _merge_sync(request: MergeRequest) -> MergeResponse:
    frames = []
    seen = set()
    for item in request.files:
        if item.job_id in seen:
            raise DataCleanError(
                "duplicate_merge_input", f"Job '{item.job_id}' is listed more than once."
            )
        seen.add(item.job_id)
        job = get_job_or_error(item.job_id)
        df = dataset_store.load_current(job["id"])
        frames.append((job["id"], job["filename"], df, item.mapping))

    merged, stats = merge_frames(frames, request.mode)

    filename = f"merged_{len(request.files)}_files.csv"
    job = repositories.create_job(
        filename=filename,
        source="merge",
        row_count=stats["output_rows"],
        column_count=stats["output_columns"],
    )
    dataset_store.save_original(job["id"], merged)
    repositories.create_run(job["id"], kind="merge", status="success", summary=stats)
    for input_job_id, _, _, _ in frames:
        repositories.create_run(
            input_job_id,
            kind="merge",
            status="success",
            summary={"merged_into": job["id"], "mode": request.mode},
        )

    return MergeResponse(
        job_id=job["id"],
        filename=filename,
        mode=request.mode,
        input_files=stats["input_files"],
        output_rows=stats["output_rows"],
        output_columns=stats["output_columns"],
        columns=stats["columns"],
        null_cells_filled=stats["null_cells_filled"],
    )
