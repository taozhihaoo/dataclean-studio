"""Pipeline step models.

A pipeline is an ordered list of steps; the backend executes enabled steps
in the exact order the client sends. Step ``type`` is a Pydantic v2
discriminated union, so an unknown type is rejected with a clean 422.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import NULL_TOKENS
from app.schemas.validation import RuleResult, ValidateConfig

NormalizationOp = Literal[
    "trim",
    "collapse_spaces",
    "lowercase",
    "uppercase",
    "title_case",
    "empty_to_null",
    "null_tokens_to_null",
    "normalize_date",
    "normalize_phone",
]


class ColumnOps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1, max_length=200)
    operations: list[NormalizationOp] = Field(min_length=1)


class NormalizeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[ColumnOps] = Field(min_length=1, max_length=200)
    date_format: str = "%Y-%m-%d"
    day_first: bool = False
    null_tokens: list[str] = Field(default_factory=lambda: list(NULL_TOKENS))


class DedupeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["exact", "columns"] = "exact"
    columns: list[str] = Field(default_factory=list)
    keep: Literal["first", "last"] = "first"


class RenameConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rename: dict[str, str] = Field(default_factory=dict)
    drop: list[str] = Field(default_factory=list)
    order: list[str] = Field(default_factory=list)


class StepBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    enabled: bool = True


class ValidateStep(StepBase):
    type: Literal["validate"] = "validate"
    config: ValidateConfig


class NormalizeStep(StepBase):
    type: Literal["normalize"] = "normalize"
    config: NormalizeConfig


class DedupeStep(StepBase):
    type: Literal["dedupe"] = "dedupe"
    config: DedupeConfig


class RenameStep(StepBase):
    type: Literal["rename"] = "rename"
    config: RenameConfig


PipelineStep = Annotated[
    ValidateStep | NormalizeStep | DedupeStep | RenameStep,
    Field(discriminator="type"),
]


class StepSample(BaseModel):
    row: int  # 1-based row number in the input dataset
    column: str | None
    before: str | None
    after: str | None


class StepReport(BaseModel):
    step_id: str
    step_type: str
    enabled: bool
    status: Literal["applied", "skipped"]
    summary: str
    input_rows: int
    output_rows: int
    stats: dict[str, Any] = Field(default_factory=dict)
    samples: list[StepSample] = Field(default_factory=list)
    removed_rows: list[dict[str, Any]] = Field(default_factory=list)


class TransformRequest(BaseModel):
    steps: list[PipelineStep] = Field(min_length=1, max_length=20)


class TransformResponse(BaseModel):
    run_id: str
    input_rows: int
    output_rows: int
    columns: list[str]
    changed_cells: int
    steps: list[StepReport]
    validation_results: list[RuleResult] = Field(default_factory=list)
    preview: list[dict[str, Any]]


class TransformPreviewResponse(BaseModel):
    input_rows: int
    output_rows: int
    columns: list[str]
    steps: list[StepReport]
    preview: list[dict[str, Any]]


PIPELINE_CONFIG_VERSION = 1


class SavedPipelineResponse(BaseModel):
    """The persisted pipeline configuration of a job.

    ``steps`` uses the exact same schema as the ``steps`` of a transform
    request, so a saved config can be replayed (and restored into the UI)
    without any client-side translation.
    """

    job_id: str
    version: int
    steps: list[PipelineStep]
    created_at: str
    updated_at: str
