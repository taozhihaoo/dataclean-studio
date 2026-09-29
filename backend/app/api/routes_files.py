"""Upload / meta routes."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile

from app.config import get_settings
from app.schemas.files import MetaResponse, UploadResponse
from app.services import inference_service, upload_service

router = APIRouter(tags=["files"])


@router.post("/api/files/upload", response_model=UploadResponse, status_code=201)
async def upload_file(upload: UploadFile) -> UploadResponse:
    outcome = await upload_service.save_and_create_job(upload, get_settings())
    return UploadResponse(
        job_id=outcome.job_id,
        filename=outcome.filename,
        size_bytes=outcome.size_bytes,
        row_count=outcome.row_count,
        column_count=outcome.column_count,
        status=outcome.status,
    )


@router.get("/api/meta", response_model=MetaResponse)
async def meta() -> MetaResponse:
    settings = get_settings()
    providers = inference_service.providers()
    return MetaResponse(
        version=settings.version,
        max_upload_mb=settings.max_upload_mb,
        preview_row_limit=settings.preview_row_limit,
        inference=providers.model_dump(),
        target_schema_suggestions=inference_service.DEFAULT_TARGET_SCHEMA,
    )
