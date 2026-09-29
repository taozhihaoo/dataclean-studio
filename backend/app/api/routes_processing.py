"""Validation, transformation and pipeline preview endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.transform import (
    TransformPreviewResponse,
    TransformRequest,
    TransformResponse,
)
from app.schemas.validation import ValidateConfig, ValidateResponse
from app.services import transformation_service

router = APIRouter(prefix="/api/jobs", tags=["processing"])


@router.post("/{job_id}/validate", response_model=ValidateResponse)
async def validate(job_id: str, config: ValidateConfig) -> ValidateResponse:
    return await transformation_service.run_validation(job_id, config)


@router.post("/{job_id}/transform", response_model=TransformResponse)
async def transform(job_id: str, request: TransformRequest) -> TransformResponse:
    return await transformation_service.run_transform(job_id, request)


@router.post("/{job_id}/transform/preview", response_model=TransformPreviewResponse)
async def transform_preview(job_id: str, request: TransformRequest) -> TransformPreviewResponse:
    return await transformation_service.preview_transform(job_id, request)
