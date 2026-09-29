"""Validation rule engine.

Rules apply to non-null values; a missing value only fails the
``required`` rule. This keeps orthogonal concerns orthogonal: a range rule
on ``age`` should not also fire on empty cells (add a ``required`` rule for
that).
"""

from __future__ import annotations

import pandas as pd

from app.core.dataframe_ops.profile import is_null
from app.core.dataframe_ops.type_inference import is_email, parse_date_series
from app.core.errors import DataCleanError
from app.core.security import compile_user_regex
from app.schemas.validation import InvalidSample, RuleResult, ValidateConfig

_MAX_SAMPLES = 5


def apply_validation(
    df: pd.DataFrame, config: ValidateConfig
) -> tuple[list[RuleResult], pd.Series]:
    """Evaluate every rule; return (results, mask of rows to drop)."""
    results: list[RuleResult] = []
    drop_mask = pd.Series(False, index=df.index)

    for rule in config.rules:
        if rule.column not in df.columns:
            raise DataCleanError(
                "unknown_column",
                f"Validation rule targets unknown column '{rule.column}'.",
                details={"column": rule.column},
            )
        series = df[rule.column]
        invalid, reasons = _evaluate_rule(series, rule)
        total_values = int((~series.map(is_null)).sum())
        error_count = int(invalid.sum())
        positions = invalid[invalid].index[:_MAX_SAMPLES]
        samples = [
            InvalidSample(
                row=int(pos) + 1,
                value=_cell(series[pos]),
                reason=str(reasons[pos]),
            )
            for pos in positions
        ]
        results.append(
            RuleResult(
                column=rule.column,
                rule=rule.rule,
                total_values=total_values,
                error_count=error_count,
                error_rate=round(error_count / total_values, 4) if total_values else 0.0,
                passed=error_count == 0,
                samples=samples,
            )
        )
        if config.drop_invalid_rows:
            drop_mask |= invalid

    return results, drop_mask


def _cell(value: object) -> str | None:
    if is_null(value):
        return None
    return str(value)


def _evaluate_rule(series: pd.Series, rule) -> tuple[pd.Series, pd.Series]:
    """Return (invalid_mask, per-row reason string for invalid rows)."""
    values = series.astype(object)
    is_missing = values.map(is_null)
    index = values.index

    def const(text: str) -> pd.Series:
        return pd.Series(text, index=index)

    if rule.rule == "required":
        invalid = is_missing
        return invalid, const("value is empty").where(invalid, "")

    non_null = ~is_missing

    if rule.rule == "email":
        invalid = non_null & values.map(lambda v: not is_email(str(v)))
        return invalid, const("not a valid email address").where(invalid, "")

    if rule.rule == "numeric_range":
        numeric = pd.to_numeric(values.where(non_null), errors="coerce")
        not_number = non_null & numeric.isna()
        below = numeric.lt(rule.min) if rule.min is not None else pd.Series(False, index=index)
        above = numeric.gt(rule.max) if rule.max is not None else pd.Series(False, index=index)
        out_of_range = non_null & ~not_number & (below | above)
        invalid = not_number | out_of_range
        low = rule.min if rule.min is not None else "-inf"
        high = rule.max if rule.max is not None else "inf"
        reasons = const("not a number").where(not_number, "")
        reasons = reasons.where(~out_of_range, const(f"value out of range [{low}, {high}]"))
        return invalid, reasons

    if rule.rule == "string_length":
        lengths = values.where(non_null).map(lambda v: len(str(v)) if v is not None else 0)
        lengths = pd.to_numeric(pd.Series(lengths, index=index), errors="coerce")
        too_short = (
            lengths.lt(rule.min_length)
            if rule.min_length is not None
            else pd.Series(False, index=index)
        )
        too_long = (
            lengths.gt(rule.max_length)
            if rule.max_length is not None
            else pd.Series(False, index=index)
        )
        invalid = non_null & (too_short | too_long)
        low = rule.min_length if rule.min_length is not None else 0
        high = rule.max_length if rule.max_length is not None else "∞"
        return invalid, const(f"length outside {low}-{high} characters").where(invalid, "")

    if rule.rule == "date":
        parsed = parse_date_series(values.where(non_null))
        invalid = non_null & parsed.isna()
        return invalid, const("not a parseable date").where(invalid, "")

    if rule.rule == "regex":
        compiled = compile_user_regex(rule.pattern or "")
        invalid = non_null & values.map(lambda v: compiled.fullmatch(str(v)) is None)
        return invalid, const("does not match the required pattern").where(invalid, "")

    if rule.rule == "allowed_values":
        allowed = set(rule.values or [])
        invalid = non_null & ~values.map(lambda v: str(v) in allowed)
        return invalid, const("value is not in the allowed set").where(invalid, "")

    raise DataCleanError("invalid_validation_rule", f"Unsupported rule '{rule.rule}'.")
