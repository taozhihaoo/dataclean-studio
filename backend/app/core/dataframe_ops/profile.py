"""Dataset profiling: per-column schema detection and quality statistics."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.dataframe_ops.type_inference import (
    TYPE_DATE,
    TYPE_DATETIME,
    TYPE_EMAIL,
    infer_column_type,
    is_email,
    parse_date_series,
)

_SAMPLE_VALUES = 3
_NULL_VALUE_SET = {None, ""}


def is_null(value: object) -> bool:
    return value is None or value == ""


def profile_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per-column profile used by schema detection and the quality report."""
    return [_profile_column(df[column]) for column in df.columns]


def _profile_column(series: pd.Series) -> dict[str, Any]:
    inferred = infer_column_type(series)
    non_null = [v for v in series.tolist() if not is_null(v)]
    profile: dict[str, Any] = {
        "name": str(series.name),
        "detected_type": inferred,
        "null_count": int(series.map(is_null).sum()),
        "unique_count": len(set(non_null)),
        "sample_values": list(dict.fromkeys(non_null))[:_SAMPLE_VALUES],
    }
    if inferred == TYPE_EMAIL:
        profile["invalid_count"] = sum(1 for v in non_null if not is_email(v))
    elif inferred in (TYPE_DATE, TYPE_DATETIME):
        parsed = parse_date_series(pd.Series(non_null, dtype=object))
        profile["invalid_count"] = int(parsed.isna().sum())
    return profile


def count_nulls(df: pd.DataFrame) -> dict[str, int]:
    return {column: int(df[column].map(is_null).sum()) for column in df.columns}


def count_invalid_emails(df: pd.DataFrame) -> int:
    total = 0
    for column in df.columns:
        if infer_column_type(df[column]) != TYPE_EMAIL:
            continue
        values = (v for v in df[column].tolist() if not is_null(v))
        total += sum(1 for v in values if not is_email(v))
    return total


def count_invalid_dates(df: pd.DataFrame) -> int:
    total = 0
    for column in df.columns:
        if infer_column_type(df[column]) not in (TYPE_DATE, TYPE_DATETIME):
            continue
        values = pd.Series([v for v in df[column].tolist() if not is_null(v)], dtype=object)
        if not values.empty:
            total += int(parse_date_series(values).isna().sum())
    return total


def count_exact_duplicates(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    return int(df.duplicated(keep="first").sum())
