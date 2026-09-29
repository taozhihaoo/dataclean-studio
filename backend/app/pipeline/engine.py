"""Pipeline engine: executes ordered cleaning steps over a DataFrame.

The engine is pure (no I/O): it takes steps + a DataFrame and produces the
resulting DataFrame plus a per-step report with before/after samples.
Every transform run starts from the original uploaded dataset, so pipelines
are idempotent and safe to re-run after edits.
"""

from __future__ import annotations

import logging

import pandas as pd

from app.core.dataframe_ops.dedupe import deduplicate
from app.core.dataframe_ops.mapping import apply_mapping
from app.core.dataframe_ops.normalizers import apply_normalization
from app.core.dataframe_ops.validation_rules import apply_validation
from app.core.errors import DataCleanError
from app.schemas.transform import (
    PipelineStep,
    StepReport,
    StepSample,
)
from app.schemas.validation import RuleResult

logger = logging.getLogger(__name__)


class PipelineEngine:
    def __init__(self, steps: list[PipelineStep]) -> None:
        ids = [step.id for step in steps]
        if len(set(ids)) != len(ids):
            duplicate = next(i for i in ids if ids.count(i) > 1)
            raise DataCleanError(
                "duplicate_pipeline_step",
                f"Pipeline contains a duplicate step id '{duplicate}'.",
                details={"step_id": duplicate},
            )
        self.steps = steps

    def run(self, df: pd.DataFrame) -> PipelineRunResult:
        current = df.copy()
        input_rows = int(len(current))
        reports: list[StepReport] = []
        validation_results: list[RuleResult] = []
        changed_cells_total = 0

        for step in self.steps:
            if not step.enabled:
                reports.append(
                    StepReport(
                        step_id=step.id,
                        step_type=step.type,
                        enabled=False,
                        status="skipped",
                        summary="Step is disabled.",
                        input_rows=int(len(current)),
                        output_rows=int(len(current)),
                    )
                )
                continue

            previous = current
            try:
                current, step_result = self._apply(step, current)
            except DataCleanError as exc:
                exc.details.setdefault("step_id", step.id)
                exc.details.setdefault("step_type", step.type)
                raise

            shape_changed = len(current) != len(previous) or list(current.columns) != list(
                previous.columns
            )
            if not shape_changed:
                changed = count_changed_cells(previous, current)
                changed_cells_total += changed

            validation: list[RuleResult] = step_result.pop("validation_results", [])
            if validation:
                validation_results.extend(validation)

            reports.append(
                StepReport(
                    step_id=step.id,
                    step_type=step.type,
                    enabled=True,
                    status="applied",
                    input_rows=int(len(previous)),
                    output_rows=int(len(current)),
                    **step_result,
                )
            )

        return PipelineRunResult(
            df=current,
            input_rows=input_rows,
            output_rows=int(len(current)),
            changed_cells=changed_cells_total,
            steps=reports,
            validation_results=validation_results,
        )

    def _apply(self, step: PipelineStep, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
        if step.type == "validate":
            results, drop_mask = apply_validation(df, step.config)
            output = df[~drop_mask] if step.config.drop_invalid_rows else df
            error_total = sum(r.error_count for r in results)
            if step.config.drop_invalid_rows:
                summary = (
                    f"{error_total} validation error(s); "
                    f"{int(drop_mask.sum())} invalid row(s) removed."
                )
            else:
                summary = f"{error_total} validation error(s) found; no rows removed."
            return output, {
                "summary": summary,
                "stats": {
                    "rules": len(step.config.rules),
                    "errors_total": error_total,
                    "rows_dropped": int(len(df) - len(output)),
                    "drop_invalid_rows": step.config.drop_invalid_rows,
                },
                "samples": _validation_samples(results),
                "removed_rows": [],
                "validation_results": results,
            }

        if step.type == "normalize":
            output, payload = apply_normalization(df, step.config)
            changed = payload["stats"]["changed_cells"]
            return output, {
                "summary": f"{changed} cell(s) normalized.",
                "stats": payload["stats"],
                "samples": payload["samples"],
                "removed_rows": [],
            }

        if step.type == "dedupe":
            output, payload = deduplicate(df, step.config)
            removed = payload["stats"]["rows_removed"]
            return output, {
                "summary": f"{removed} duplicate row(s) removed ({step.config.keep} kept).",
                "stats": payload["stats"],
                "samples": payload["samples"],
                "removed_rows": payload["removed_rows"],
            }

        if step.type == "rename":
            output, payload = apply_mapping(df, step.config)
            renamed = payload["stats"]["renamed"]
            dropped = payload["stats"]["dropped"]
            return output, {
                "summary": (
                    f"{len(renamed)} column(s) renamed, {len(dropped)} dropped,"
                    f" {len(output.columns)} column(s) in output."
                ),
                "stats": payload["stats"],
                "samples": payload["samples"],
                "removed_rows": [],
            }

        raise DataCleanError("invalid_pipeline", f"Unsupported step type '{step.type}'.")


def _validation_samples(results: list[RuleResult], limit: int = 5) -> list[StepSample]:
    samples: list[StepSample] = []
    for result in results:
        for sample in result.samples:
            if len(samples) >= limit:
                return samples
            samples.append(
                StepSample(
                    row=sample.row,
                    column=result.column,
                    before=sample.value,
                    after=None,
                )
            )
    return samples


def count_changed_cells(before: pd.DataFrame, after: pd.DataFrame) -> int:
    if list(before.columns) != list(after.columns) or len(before) != len(after):
        return 0
    changed = 0
    for column in before.columns:
        left = before[column].where(before[column].notna(), "")
        right = after[column].where(after[column].notna(), "")
        changed += int((left.astype(str) != right.astype(str)).sum())
    return changed


class PipelineRunResult:
    def __init__(
        self,
        df: pd.DataFrame,
        input_rows: int,
        output_rows: int,
        changed_cells: int,
        steps: list[StepReport],
        validation_results: list[RuleResult],
    ) -> None:
        self.df = df
        self.input_rows = input_rows
        self.output_rows = output_rows
        self.changed_cells = changed_cells
        self.steps = steps
        self.validation_results = validation_results
