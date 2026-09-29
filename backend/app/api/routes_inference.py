"""Optional schema-inference endpoints (heuristic by default, AI opt-in)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.operations import (
    InferenceProvidersResponse,
    InferMappingRequest,
    InferMappingResponse,
)
from app.services import inference_service

router = APIRouter(tags=["inference"])


@router.get("/api/inference/providers", response_model=InferenceProvidersResponse)
async def providers() -> InferenceProvidersResponse:
    return inference_service.providers()


@router.post("/api/jobs/{job_id}/infer-mapping", response_model=InferMappingResponse)
async def infer_mapping(job_id: str, request: InferMappingRequest) -> InferMappingResponse:
    return await inference_service.suggest_mapping(job_id, request)
