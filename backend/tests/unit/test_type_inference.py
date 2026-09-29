import pandas as pd

from app.core.dataframe_ops.type_inference import (
    TYPE_BOOLEAN,
    TYPE_DATE,
    TYPE_DATETIME,
    TYPE_EMAIL,
    TYPE_EMPTY,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_PHONE,
    TYPE_STRING,
    infer_column_type,
    is_email,
    is_phone_like,
    parse_date_series,
)


def series(*values):
    return pd.Series(list(values), dtype=object)


class TestInferColumnType:
    def test_integer(self):
        assert infer_column_type(series("1", "2", "-30", "")) == TYPE_INTEGER

    def test_float(self):
        assert infer_column_type(series("1.5", "2", "-0.3")) == TYPE_FLOAT

    def test_boolean(self):
        assert infer_column_type(series("true", "false", "yes", "no")) == TYPE_BOOLEAN

    def test_date(self):
        assert infer_column_type(series("2025-01-15", "01/20/2025", "")) == TYPE_DATE

    def test_datetime_with_time_component(self):
        assert infer_column_type(series("2025-01-15 10:30:00", "2025-01-16 09:00")) == TYPE_DATETIME

    def test_email(self):
        assert (
            infer_column_type(series("a@x.com", "b@y.org", "c@z.net", "not-an-email", ""))
            == TYPE_EMAIL
        )

    def test_phone(self):
        assert (
            infer_column_type(series("+1 (555) 010-1234", "555-010-5678", "5551234567"))
            == TYPE_PHONE
        )

    def test_string_fallback(self):
        assert infer_column_type(series("apple", "banana")) == TYPE_STRING

    def test_empty_column(self):
        assert infer_column_type(series("", "", None)) == TYPE_EMPTY

    def test_majority_integer_with_one_junk(self):
        assert (
            infer_column_type(series("1", "2", "3", "4", "5", "6", "7", "8", "9", "x"))
            == TYPE_INTEGER
        )

    def test_numeric_column_not_detected_as_date(self):
        assert infer_column_type(series("2025", "2026", "2027")) == TYPE_INTEGER

    def test_mixed_stays_string(self):
        assert infer_column_type(series("a@x.com", "555-1234", "hello")) == TYPE_STRING


class TestEmailCheck:
    def test_valid(self):
        assert is_email("john.doe+tag@example.co.uk")

    def test_invalid(self):
        assert not is_email("john@@example")
        assert not is_email("@missing-local.com")
        assert not is_email("user@nodot")
        assert not is_email("")


class TestPhoneLike:
    def test_common_formats(self):
        for value in ("+1 (555) 010-1234", "555.010.5678", "5551234567", "555/010/2222"):
            assert is_phone_like(value)

    def test_too_short(self):
        assert not is_phone_like("123")

    def test_letters_rejected(self):
        assert not is_phone_like("555-CALL-NOW")


class TestParseDateSeries:
    def test_mixed_formats(self):
        parsed = parse_date_series(series("2025-01-15", "01/20/2025", "Jan 25, 2025"))
        assert parsed.notna().all()
        assert parsed[0].strftime("%Y-%m-%d") == "2025-01-15"
        assert parsed[1].strftime("%Y-%m-%d") == "2025-01-20"
        assert parsed[2].strftime("%Y-%m-%d") == "2025-01-25"

    def test_unparseable_is_nat(self):
        parsed = parse_date_series(series("not-a-date", "2025-01-15"))
        assert parsed.isna().iloc[0]
        assert parsed.notna().iloc[1]

    def test_day_first(self):
        parsed = parse_date_series(series("05/03/2025"), day_first=True)
        assert parsed.iloc[0].strftime("%Y-%m-%d") == "2025-03-05"

    def test_ambiguous_defaults_to_month_first(self):
        parsed = parse_date_series(series("05/03/2025"), day_first=False)
        assert parsed.iloc[0].strftime("%Y-%m-%d") == "2025-05-03"
