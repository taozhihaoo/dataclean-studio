"""Pydantic DTOs shared by the API layer and the data-ops modules."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RuleType = Literal[
    "required",
    "email",
    "numeric_range",
    "string_length",
    "date",
    "regex",
    "allowed_values",
]

RULE_LABELS: dict[str, str] = {
    "required": "Required (not null)",
    "email": "Valid email address",
    "numeric_range": "Numeric range",
    "string_length": "String length",
    "date": "Parseable date",
    "regex": "Matches regex",
    "allowed_values": "Allowed values",
}


class ValidationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1, max_length=200)
    rule: RuleType
    min: float | None = None
    max: float | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    pattern: str | None = None
    values: list[str] | None = None

    @model_validator(mode="after")
    def _check_params(self) -> ValidationRule:
        if self.rule == "numeric_range" and self.min is None and self.max is None:
            raise ValueError("numeric_range requires 'min' and/or 'max'")
        if self.rule == "string_length" and self.min_length is None and self.max_length is None:
            raise ValueError("string_length requires 'min_length' and/or 'max_length'")
        if self.rule == "regex" and not self.pattern:
            raise ValueError("regex rule requires 'pattern'")
        if self.rule == "allowed_values" and not self.values:
            raise ValueError("allowed_values rule requires a non-empty 'values' list")
        if self.rule == "numeric_range" and (
            self.min is not None and self.max is not None and self.min > self.max
        ):
            raise ValueError("'min' must be <= 'max'")
        if self.rule == "string_length" and (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("'min_length' must be <= 'max_length'")
        return self


class InvalidSample(BaseModel):
    row: int  # 1-based row number in the dataset
    value: str | None
    reason: str


class RuleResult(BaseModel):
    column: str
    rule: RuleType
    total_values: int
    error_count: int
    error_rate: float
    passed: bool
    samples: list[InvalidSample]


class ValidateConfig(BaseModel):
    rules: list[ValidationRule] = Field(min_length=1, max_length=100)
    drop_invalid_rows: bool = False


class ValidateResponse(BaseModel):
    total_rows: int
    error_count_total: int
    rows_dropped: int
    passed: bool
    rules: list[RuleResult]
    output_rows: int
