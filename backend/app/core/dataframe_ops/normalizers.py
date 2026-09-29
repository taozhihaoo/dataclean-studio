"""Text / null / date / phone normalization operations.

All operations work on the canonical string DataFrame: nulls stay null,
text operations skip them, and normalization only rewrites values it can
parse (e.g. an unparseable date is kept as-is and counted, never dropped).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.core.dataframe_ops.profile import is_null
from app.core.dataframe_ops.type_inference import parse_date_series
from app.core.errors import DataCleanError
from app.schemas.transform import NormalizeConfig

_TEXT_OPS = {"trim", "collapse_spaces", "lowercase", "uppercase", "title_case"}


def apply_normalization(df: pd.DataFrame, config: NormalizeConfig) -> tuple[pd.DataFrame, dict]:
    """Apply per-column operation chains; return (new_df, stats)."""
    result = df.copy()
    per_column: dict[str, dict] = {}

    seen = set()
    for column_ops in config.columns:
        column = column_ops.column
        if column not in df.columns:
            raise DataCleanError(
                "unknown_column",
                f"Normalization targets unknown column '{column}'.",
                details={"column": column},
            )
        if column in seen:
            raise DataCleanError(
                "duplicate_column_operation",
                f"Column '{column}' appears more than once in the normalize step.",
                details={"column": column},
            )
        seen.add(column)

        series = result[column]
        counts: dict[str, int] = {}
        for operation in column_ops.operations:
            series, applied = _apply_operation(series, operation, config)
            if applied:
                counts[operation] = applied
        result[column] = series
        if counts:
            per_column[column] = counts
        if column_ops.operations and not counts:
            per_column[column] = {"no_changes": len(df)}

    changed_cells, samples = _diff(df, result)
    stats = {"changed_cells": changed_cells, "per_column": per_column}
    return result, {"stats": stats, "samples": samples, "removed_rows": []}


def _apply_operation(
    series: pd.Series, operation: str, config: NormalizeConfig
) -> tuple[pd.Series, int]:
    before = series.copy()
    null_mask = series.map(is_null)
    text = series.where(~null_mask, "")  # None and "" as empty strings for str ops

    if operation in _TEXT_OPS:
        if operation == "trim":
            text = text.str.strip()
        elif operation == "collapse_spaces":
            text = text.str.replace(r"\s+", " ", regex=True)
        elif operation == "lowercase":
            text = text.str.lower()
        elif operation == "uppercase":
            text = text.str.upper()
        elif operation == "title_case":
            text = text.str.title()
        # restore the original null representation (None stays None, "" stays "")
        series = text.where(~null_mask, series)
    elif operation == "empty_to_null":
        series = series.copy()
        series[series == ""] = None
    elif operation == "null_tokens_to_null":
        tokens = {token.strip().lower() for token in config.null_tokens}
        stripped = text.str.strip().str.lower()
        series = series.copy()
        series[stripped.isin(tokens)] = None
    elif operation == "normalize_date":
        series = _normalize_dates(series, config)
    elif operation == "normalize_phone":
        cleaned = text.str.replace(r"[^\d+]", "", regex=True)
        series = cleaned.where(~null_mask, series)
    else:  # guarded by the schema Literal; kept for safety
        raise DataCleanError("invalid_operation", f"Unknown normalization op '{operation}'.")

    applied = int(_column_changed(before, series).sum())
    return series, applied


def _normalize_dates(series: pd.Series, config: NormalizeConfig) -> pd.Series:
    non_null = ~series.map(is_null)
    try:
        # strftime in pandas swallows bad directives; validate the format
        # with stdlib first so users get a clean error.
        datetime(2025, 1, 15, 13, 30, 45).strftime(config.date_format)
        parsed = parse_date_series(series.where(non_null), day_first=config.day_first)
        formatted = parsed.dt.strftime(config.date_format)
    except ValueError as exc:
        raise DataCleanError(
            "invalid_date_format",
            f"Invalid date_format '{config.date_format}': {exc}",
        ) from exc
    result = series.astype(object).copy()
    writable = non_null & parsed.notna()
    result[writable] = formatted[writable]
    return result


def _column_changed(before: pd.Series, after: pd.Series) -> pd.Series:
    norm_before = before.where(before.notna(), "").astype(str)
    norm_after = after.where(after.notna(), "").astype(str)
    return norm_before != norm_after


def _diff(
    before_df: pd.DataFrame, after_df: pd.DataFrame, max_samples: int = 5
) -> tuple[int, list[dict]]:
    """Cell-level diff between two same-shape frames; returns (count, samples)."""
    changed = 0
    samples: list[dict] = []
    for column in before_df.columns:
        mask = _column_changed(before_df[column], after_df[column])
        if not mask.any():
            continue
        changed += int(mask.sum())
        if len(samples) >= max_samples:
            continue
        for pos in mask[mask].index:
            if len(samples) >= max_samples:
                break
            samples.append(
                {
                    "row": int(pos) + 1,
                    "column": column,
                    "before": _display(before_df.at[pos, column]),
                    "after": _display(after_df.at[pos, column]),
                }
            )
    return changed, samples


def _display(value: object) -> str | None:
    if is_null(value):
        return None
    return str(value)
