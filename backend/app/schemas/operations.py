"""Merge / export / inference DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MergeFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    mapping: dict[str, str] = Field(default_factory=dict)


class MergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[MergeFileInput] = Field(min_length=2, max_length=20)
    mode: Literal["union", "intersection"] = "union"


class FileMergeStat(BaseModel):
    job_id: str
    filename: str
    rows: int
    columns: int


class MergeResponse(BaseModel):
    job_id: str
    filename: str
    mode: str
    input_files: list[FileMergeStat]
    output_rows: int
    output_columns: int
    columns: list[str]
    null_cells_filled: int


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_format: Literal["csv", "json", "xlsx"] = "csv"
    filename: str | None = Field(default=None, max_length=100)
    guard_formulas: bool = True


class MappingSuggestionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    target: str
    confidence: float
    rationale: str
    provider: str


class InferMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_schema: list[str] = Field(default_factory=list, max_length=50)
    provider: str = "heuristic"


class InferMappingResponse(BaseModel):
    provider: str
    suggestions: list[MappingSuggestionDTO]
    targets_used: list[str]


class InferenceProvidersResponse(BaseModel):
    default: str
    available: list[str]
    openai_configured: bool
