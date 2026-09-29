"""Schema-inference orchestration: always heuristic-first, AI opt-in."""

from __future__ import annotations

import logging

from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.core.inference.base import ColumnSample
from app.core.inference.registry import HEURISTIC, available_providers, get_provider
from app.schemas.operations import (
    InferenceProvidersResponse,
    InferMappingRequest,
    InferMappingResponse,
    MappingSuggestionDTO,
)
from app.services import dataset_store
from app.services.job_service import get_job_or_error

logger = logging.getLogger(__name__)

# Curated canonical fields offered in the UI and understood by the
# heuristic synonym table.
DEFAULT_TARGET_SCHEMA = [
    "customer_id",
    "customer_name",
    "email",
    "phone",
    "age",
    "status",
    "created_at",
    "city",
    "country",
    "address",
    "company",
    "amount",
    "order_id",
    "order_date",
    "first_name",
    "last_name",
]

_MAX_SAMPLE_VALUES = 3


def providers() -> InferenceProvidersResponse:
    settings = get_settings()
    return InferenceProvidersResponse(
        default=HEURISTIC,
        available=available_providers(settings),
        openai_configured=bool(settings.openai_api_key),
    )


async def suggest_mapping(job_id: str, request: InferMappingRequest) -> InferMappingResponse:
    return await run_in_threadpool(_suggest_sync, job_id, request)


def _suggest_sync(job_id: str, request: InferMappingRequest) -> InferMappingResponse:
    job = get_job_or_error(job_id)
    settings = get_settings()
    df = dataset_store.load_current(job_id)

    targets = [t.strip() for t in request.target_schema if t.strip()] or DEFAULT_TARGET_SCHEMA
    columns = [
        ColumnSample(
            name=str(column),
            sample_values=[
                str(v) for v in df[column].dropna().unique()[:_MAX_SAMPLE_VALUES] if str(v).strip()
            ],
        )
        for column in df.columns
    ]

    provider = get_provider(request.provider or HEURISTIC, settings)
    suggestions = provider.suggest(columns, targets)
    logger.info(
        "Inference for job %s (%s) via %s: %d suggestion(s)",
        job["id"],
        job["filename"],
        provider.name,
        len(suggestions),
    )
    return InferMappingResponse(
        provider=provider.name,
        suggestions=[
            MappingSuggestionDTO.model_validate(s, from_attributes=True) for s in suggestions
        ],
        targets_used=targets,
    )


def target_schema_suggestions() -> list[str]:
    return list(DEFAULT_TARGET_SCHEMA)


def provider_names(settings: Settings) -> list[str]:
    return available_providers(settings)
