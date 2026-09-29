"""Job listing, detail, preview, runs and deletion."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.db import repositories
from app.schemas.files import (
    DeleteResponse,
    JobDetail,
    JobSummary,
    PreviewResponse,
    RunSummary,
)
from app.services import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

JobId = Annotated[str, Path(min_length=8, max_length=64)]


@router.get("", response_model=list[JobSummary])
async def list_jobs() -> list[JobSummary]:
    return [
        JobSummary(
            job_id=job["id"],
            filename=job["filename"],
            source=job["source"],
            status=job["status"],
            row_count=job["row_count"],
            column_count=job["column_count"],
            created_at=job["created_at"],
            updated_at=job["updated_at"],
        )
        for job in repositories.list_jobs()
    ]


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: JobId) -> JobDetail:
    job = job_service.get_job_or_error(job_id)
    return JobDetail(**job_service.job_detail(job))


@router.delete("/{job_id}", response_model=DeleteResponse)
async def delete_job(job_id: JobId) -> DeleteResponse:
    job_service.delete_job(job_id)
    return DeleteResponse(job_id=job_id, deleted=True)


@router.get("/{job_id}/preview", response_model=PreviewResponse)
async def preview(
    job_id: JobId, limit: Annotated[int | None, Query(ge=1, le=200)] = None
) -> PreviewResponse:
    job = job_service.get_job_or_error(job_id)
    return PreviewResponse(**job_service.job_preview(job, limit))


@router.get("/{job_id}/runs", response_model=list[RunSummary])
async def job_runs(job_id: JobId, kind: Annotated[str | None, Query()] = None) -> list[RunSummary]:
    job_service.get_job_or_error(job_id)
    return [
        RunSummary(
            run_id=run["id"],
            job_id=run["job_id"],
            kind=run["kind"],
            status=run["status"],
            created_at=run["created_at"],
            summary=run["summary"],
        )
        for run in repositories.list_runs(job_id, kind=kind)
    ]
