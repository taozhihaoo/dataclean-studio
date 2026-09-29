import pandas as pd

from app.core.dataframe_ops.profile import (
    count_exact_duplicates,
    count_invalid_dates,
    count_invalid_emails,
    count_nulls,
    profile_dataframe,
)


def make_frame(**columns):
    return pd.DataFrame({k: pd.Series(v, dtype=object) for k, v in columns.items()})


class TestProfile:
    def test_nulls_uniques_samples(self):
        df = make_frame(name=["Ann", "Bob", "Ann", "", ""])
        profile = profile_dataframe(df)[0]
        assert profile["name"] == "name"
        assert profile["detected_type"] == "string"
        assert profile["null_count"] == 2
        assert profile["unique_count"] == 2
        assert profile["sample_values"] == ["Ann", "Bob"]

    def test_email_invalid_count(self):
        df = make_frame(mail=["a@x.com", "b@x.com", "c@x.com", "d@x.com", "broken", ""])
        profile = profile_dataframe(df)[0]
        assert profile["detected_type"] == "email"
        assert profile["invalid_count"] == 1

    def test_date_invalid_count(self):
        valid = [f"2025-01-{d:02d}" for d in range(1, 8)] + ["2025-02-01", "2025-02-02"]
        df = make_frame(d=[*valid, "garbage", ""])
        profile = profile_dataframe(df)[0]
        assert profile["detected_type"] == "date"
        assert profile["invalid_count"] == 1


class TestQualityCounters:
    def test_count_nulls(self):
        df = make_frame(a=["x", "", None], b=["", "", ""])
        assert count_nulls(df) == {"a": 2, "b": 3}

    def test_count_invalid_emails_only_email_columns(self):
        df = make_frame(
            mail=["a@x.com", "b@x.com", "c@x.com", "bad"], note=["not-email", "also", "x", "y"]
        )
        assert count_invalid_emails(df) == 1

    def test_count_invalid_dates_only_date_columns(self):
        valid = [f"2025-01-{d:02d}" for d in range(1, 10)]
        df = make_frame(
            d=[*valid, "junk"],
            text=["2025-01-01", "junk", "x", "y", "z", "p", "q", "r", "s", "t"],
        )
        assert count_invalid_dates(df) == 1

    def test_count_exact_duplicates(self):
        df = make_frame(a=["1", "1", "2"], b=["x", "x", "y"])
        assert count_exact_duplicates(df) == 1
        assert count_exact_duplicates(make_frame(a=["1"], b=["x"])) == 0
        assert count_exact_duplicates(make_frame(a=[], b=[])) == 0
