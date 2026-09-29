"""Export, quality report and merge endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.schemas.operations import ExportRequest, MergeRequest, MergeResponse
from app.services import export_service, merge_service, quality_report_service

router = APIRouter(tags=["output"])


@router.post("/api/jobs/{job_id}/export")
async def export(job_id: str, request: ExportRequest) -> FileResponse:
    result = await export_service.export_job(job_id, request)
    return FileResponse(
        path=result.path,
        media_type=result.media_type,
        filename=result.filename,
    )


@router.get("/api/jobs/{job_id}/quality-report")
async def quality_report(job_id: str) -> dict:
    return await quality_report_service.build_report(job_id)


@router.post("/api/merge", response_model=MergeResponse, status_code=201)
async def merge(request: MergeRequest) -> MergeResponse:
    return await merge_service.merge(request)
