"""Pydantic DTOs for uploads, jobs, previews and runs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    size_bytes: int
    row_count: int
    column_count: int
    status: str


class ColumnProfileDTO(BaseModel):
    name: str
    detected_type: str
    null_count: int
    unique_count: int
    sample_values: list[str]
    invalid_count: int | None = None


class JobSummary(BaseModel):
    job_id: str
    filename: str
    source: str
    status: str
    row_count: int | None
    column_count: int | None
    created_at: str
    updated_at: str


class JobDetail(JobSummary):
    size_bytes: int | None = None
    is_transformed: bool
    columns: list[ColumnProfileDTO]


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    limited: bool


class RunSummary(BaseModel):
    run_id: str
    job_id: str
    kind: str
    status: str
    created_at: str
    summary: dict[str, Any] | None = None


class DeleteResponse(BaseModel):
    job_id: str
    deleted: bool


class MetaResponse(BaseModel):
    version: str
    max_upload_mb: int
    preview_row_limit: int
    inference: dict[str, Any]
    target_schema_suggestions: list[str] = Field(default_factory=list)
