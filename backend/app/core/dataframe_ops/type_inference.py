"""Best-effort column type inference.

The inferred type is a heuristic, not a guarantee (always reported as
"detected type" in the UI). Detection order matters: more specific formats
are tested before generic ones.
"""

from __future__ import annotations

import re

import pandas as pd

INTEGER_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")
BOOLEAN_TOKENS = {"true", "false", "yes", "no", "y", "n", "t", "f"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[\d\s()./\-]{7,25}$")

TYPE_INTEGER = "integer"
TYPE_FLOAT = "float"
TYPE_BOOLEAN = "boolean"
TYPE_DATE = "date"
TYPE_DATETIME = "datetime"
TYPE_EMAIL = "email"
TYPE_PHONE = "phone"
TYPE_STRING = "string"
TYPE_EMPTY = "empty"

_RATIO_THRESHOLD = 0.90
_EMAIL_PHONE_THRESHOLD = 0.70
_MAX_DATE_SAMPLE = 200


def is_email(value: str) -> bool:
    return bool(value) and EMAIL_RE.match(value) is not None


def is_phone_like(value: str) -> bool:
    if not value or not PHONE_RE.match(value):
        return False
    digit_count = sum(ch.isdigit() for ch in value)
    return 7 <= digit_count <= 15


def parse_date_series(series: pd.Series, day_first: bool = False) -> pd.Series:
    """Parse a string series into datetimes; unparseable values become NaT.

    ``format="mixed"`` lets each value use its own layout, which is exactly
    what a cleaning tool faces (ISO dates next to 01/20/2025 next to
    "Jan 25, 2025").
    """
    cleaned = series.where(series.notna(), None)
    return pd.to_datetime(cleaned, errors="coerce", format="mixed", dayfirst=day_first, utc=False)


def infer_column_type(series: pd.Series) -> str:
    values = [v for v in series.tolist() if isinstance(v, str) and v.strip() != ""]
    if not values:
        return TYPE_EMPTY
    total = len(values)

    def ratio(predicate) -> float:
        return sum(1 for v in values if predicate(v)) / total

    if ratio(lambda v: INTEGER_RE.match(v) is not None) >= _RATIO_THRESHOLD:
        return TYPE_INTEGER
    if ratio(lambda v: FLOAT_RE.match(v) is not None) >= _RATIO_THRESHOLD:
        return TYPE_FLOAT
    if ratio(lambda v: v.strip().lower() in BOOLEAN_TOKENS) >= _RATIO_THRESHOLD:
        return TYPE_BOOLEAN

    unique_sample = list(dict.fromkeys(values))[:_MAX_DATE_SAMPLE]
    if not all(INTEGER_RE.match(v) for v in unique_sample):
        parsed = parse_date_series(pd.Series(unique_sample, dtype=object))
        parsed_ratio = parsed.notna().mean()
        if parsed_ratio >= _RATIO_THRESHOLD:
            hours = parsed.dt.hour.fillna(0)
            minutes = parsed.dt.minute.fillna(0)
            seconds = parsed.dt.second.fillna(0)
            has_time = (hours != 0) | (minutes != 0) | (seconds != 0)
            return TYPE_DATETIME if bool(has_time.any()) else TYPE_DATE

    if ratio(is_email) >= _EMAIL_PHONE_THRESHOLD:
        return TYPE_EMAIL
    if ratio(is_phone_like) >= _EMAIL_PHONE_THRESHOLD:
        return TYPE_PHONE
    return TYPE_STRING
