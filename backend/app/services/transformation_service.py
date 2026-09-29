"""Validate / transform orchestration on top of the pipeline engine.

Every transform run starts from the original parsed dataset
(`original.pkl`), applies the full configured pipeline, and stores the
result as `current.pkl`. Re-running an edited pipeline therefore
overwrites the previous result instead of compounding steps.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.core.dataframe_ops import parsers
from app.core.dataframe_ops.validation_rules import apply_validation
from app.db import repositories
from app.pipeline.engine import PipelineEngine
from app.schemas.transform import (
    TransformPreviewResponse,
    TransformRequest,
    TransformResponse,
)
from app.schemas.validation import ValidateConfig, ValidateResponse
from app.services import dataset_store
from app.services.job_service import get_job_or_error

logger = logging.getLogger(__name__)

_PREVIEW_ROW_LIMIT = 50
_PREVIEW_MAX_ROWS = 200


async def run_transform(job_id: str, request: TransformRequest) -> TransformResponse:
    return await run_in_threadpool(_run_transform_sync, job_id, request)


def _run_transform_sync(job_id: str, request: TransformRequest) -> TransformResponse:
    get_job_or_error(job_id)
    engine = PipelineEngine(request.steps)
    original = dataset_store.load_original(job_id)
    outcome = engine.run(original)

    dataset_store.save_current(job_id, outcome.df)
    repositories.update_job(
        job_id,
        status="transformed",
        row_count=outcome.output_rows,
        column_count=len(outcome.df.columns),
    )
    run_id = repositories.create_run(
        job_id,
        kind="transform",
        status="success",
        summary={
            "input_rows": outcome.input_rows,
            "output_rows": outcome.output_rows,
            "changed_cells": outcome.changed_cells,
            "steps": [
                {"id": s.step_id, "type": s.step_type, "status": s.status, "summary": s.summary}
                for s in outcome.steps
            ],
        },
    )
    return TransformResponse(
        run_id=run_id,
        input_rows=outcome.input_rows,
        output_rows=outcome.output_rows,
        columns=[str(c) for c in outcome.df.columns],
        changed_cells=outcome.changed_cells,
        steps=outcome.steps,
        validation_results=outcome.validation_results,
        preview=parsers.dataframe_to_records(outcome.df.head(_PREVIEW_ROW_LIMIT)),
    )


async def preview_transform(job_id: str, request: TransformRequest) -> TransformPreviewResponse:
    return await run_in_threadpool(_preview_transform_sync, job_id, request)


def _preview_transform_sync(job_id: str, request: TransformRequest) -> TransformPreviewResponse:
    get_job_or_error(job_id)
    engine = PipelineEngine(request.steps)
    original = dataset_store.load_original(job_id)
    sample = original.head(_PREVIEW_MAX_ROWS)
    outcome = engine.run(sample)
    return TransformPreviewResponse(
        input_rows=outcome.input_rows,
        output_rows=outcome.output_rows,
        columns=[str(c) for c in outcome.df.columns],
        steps=outcome.steps,
        preview=parsers.dataframe_to_records(outcome.df.head(_PREVIEW_ROW_LIMIT)),
    )


async def run_validation(job_id: str, config: ValidateConfig) -> ValidateResponse:
    return await run_in_threadpool(_run_validation_sync, job_id, config)


def _run_validation_sync(job_id: str, config: ValidateConfig) -> ValidateResponse:
    get_job_or_error(job_id)
    df = dataset_store.load_current(job_id)
    results, drop_mask = apply_validation(df, config)

    rows_dropped = 0
    if config.drop_invalid_rows:
        filtered = df[~drop_mask]
        rows_dropped = int(len(df) - len(filtered))
        if rows_dropped:
            dataset_store.save_current(job_id, filtered)
            repositories.update_job(
                job_id,
                status="transformed",
                row_count=int(len(filtered)),
                column_count=len(filtered.columns),
            )

    error_total = sum(r.error_count for r in results)
    repositories.create_run(
        job_id,
        kind="validate",
        status="success",
        summary={
            "rules": len(config.rules),
            "errors_total": error_total,
            "rows_dropped": rows_dropped,
            "dropped_rows_applied": config.drop_invalid_rows and rows_dropped > 0,
        },
    )
    return ValidateResponse(
        total_rows=int(len(df)),
        error_count_total=error_total,
        rows_dropped=rows_dropped,
        passed=error_total == 0,
        rules=results,
        output_rows=int(len(df)) - rows_dropped,
    )


def last_run(job_id: str, kind: str) -> dict[str, Any] | None:
    runs = repositories.list_runs(job_id, kind=kind)
    return runs[0] if runs else None
