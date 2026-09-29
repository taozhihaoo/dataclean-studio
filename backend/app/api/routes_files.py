"""Upload / meta routes."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.config import get_settings
from app.schemas.files import (
    BatchUploadResponse,
    BatchUploadResult,
    MetaResponse,
    UploadResponse,
)
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


@router.post("/api/files/upload-batch", response_model=BatchUploadResponse)
async def upload_files_batch(
    files: list[UploadFile] = File(min_length=1),
) -> BatchUploadResponse:
    settings = get_settings()
    if len(files) > upload_service.MAX_BATCH_FILES:
        from app.core.errors import DataCleanError

        raise DataCleanError(
            "batch_too_many_files",
            f"A batch is limited to {upload_service.MAX_BATCH_FILES} files"
            f" (received {len(files)}).",
            status_code=400,
        )
    outcomes = await upload_service.save_batch_and_create_jobs(files, settings)
    results = [
        BatchUploadResult(
            filename=item.filename,
            stored_filename=item.stored_filename,
            status=item.status,
            job_id=item.job_id,
            row_count=item.row_count,
            column_count=item.column_count,
            size_bytes=item.size_bytes,
            error=item.error,
        )
        for item in outcomes
    ]
    uploaded = sum(1 for r in results if r.status == "uploaded")
    return BatchUploadResponse(results=results, uploaded=uploaded, failed=len(results) - uploaded)


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
