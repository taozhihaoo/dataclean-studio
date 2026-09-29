import pandas as pd
import pytest

from app.core.dataframe_ops.normalizers import apply_normalization
from app.core.errors import DataCleanError
from app.schemas.transform import ColumnOps, NormalizeConfig


def normalize(frame, column, *operations, **kwargs):
    config = NormalizeConfig(
        columns=[ColumnOps(column=column, operations=list(operations))], **kwargs
    )
    result, payload = apply_normalization(frame, config)
    return result, payload


def frame(**cols):
    return pd.DataFrame({k: pd.Series(v, dtype=object) for k, v in cols.items()})


class TestTextOperations:
    def test_trim(self):
        df = frame(name=["  Jo  ", "Al", ""])
        result, payload = normalize(df, "name", "trim")
        assert result["name"].tolist() == ["Jo", "Al", ""]
        assert payload["stats"]["changed_cells"] == 1

    def test_collapse_spaces(self):
        df = frame(name=["Jo   hn", "A  B"])
        result, _ = normalize(df, "name", "collapse_spaces")
        assert result["name"].tolist() == ["Jo hn", "A B"]

    def test_lowercase(self):
        df = frame(name=["JO", "MiXeD"])
        result, _ = normalize(df, "name", "lowercase")
        assert result["name"].tolist() == ["jo", "mixed"]

    def test_uppercase(self):
        df = frame(name=["jo", "mixed"])
        result, _ = normalize(df, "name", "uppercase")
        assert result["name"].tolist() == ["JO", "MIXED"]

    def test_title_case(self):
        df = frame(name=["john o'brien", "MARY-jane"])
        result, _ = normalize(df, "name", "title_case")
        assert result["name"].tolist() == ["John O'Brien", "Mary-Jane"]

    def test_operations_compose_in_order(self):
        df = frame(name=["  JOHN SMITH  "])
        result, payload = normalize(df, "name", "trim", "lowercase")
        assert result["name"].tolist() == ["john smith"]
        samples = payload["samples"]
        assert samples[0]["before"] == "  JOHN SMITH  "
        assert samples[0]["after"] == "john smith"


class TestNullOperations:
    def test_empty_to_null(self):
        df = frame(a=["x", "", "y"])
        result, _ = normalize(df, "a", "empty_to_null")
        assert result["a"].tolist() == ["x", None, "y"]

    def test_null_tokens_to_null(self):
        df = frame(a=["x", "N/A", "NULL", "none", "y"])
        result, _ = normalize(df, "a", "null_tokens_to_null")
        assert result["a"].tolist() == ["x", None, None, None, "y"]

    def test_custom_null_tokens(self):
        df = frame(a=["x", "MISSING"])
        result, _ = normalize(df, "a", "null_tokens_to_null", null_tokens=["missing"])
        assert result["a"].tolist() == ["x", None]

    def test_nulls_skip_text_ops(self):
        df = frame(a=[None, "  x  "])
        result, _ = normalize(df, "a", "trim")
        assert result["a"].tolist() == [None, "x"]


class TestDateNormalization:
    def test_mixed_formats_to_iso(self):
        df = frame(d=["2025-01-15", "01/20/2025", "Jan 25, 2025"])
        result, payload = normalize(df, "d", "normalize_date")
        assert result["d"].tolist() == ["2025-01-15", "2025-01-20", "2025-01-25"]
        assert payload["stats"]["changed_cells"] == 2

    def test_unparseable_value_is_kept(self):
        df = frame(d=["2025-01-15", "still-not-a-date"])
        result, _ = normalize(df, "d", "normalize_date")
        assert result["d"].tolist() == ["2025-01-15", "still-not-a-date"]

    def test_day_first_option(self):
        df = frame(d=["05/03/2025"])
        result, _ = normalize(df, "d", "normalize_date", day_first=True)
        assert result["d"].tolist() == ["2025-03-05"]

    def test_custom_format(self):
        df = frame(d=["2025-01-15"])
        result, _ = normalize(df, "d", "normalize_date", date_format="%d/%m/%Y")
        assert result["d"].tolist() == ["15/01/2025"]

    def test_invalid_format_raises_clean_error(self):
        df = frame(d=["2025-01-15"])
        with pytest.raises(DataCleanError) as excinfo:
            normalize(df, "d", "normalize_date", date_format="%Q-bogus")
        assert excinfo.value.code == "invalid_date_format"


class TestPhoneNormalization:
    def test_strips_separators(self):
        df = frame(ph=["+1 (555) 010-1234", "555.010.5678", "555/010/2222", "555 010 3333"])
        result, payload = normalize(df, "ph", "normalize_phone")
        assert result["ph"].tolist() == ["+15550101234", "5550105678", "5550102222", "5550103333"]
        assert payload["stats"]["changed_cells"] == 4

    def test_empty_stays_empty(self):
        df = frame(ph=["", "555-1234"])
        result, _ = normalize(df, "ph", "normalize_phone")
        assert result["ph"].tolist() == ["", "5551234"]


class TestConfigErrors:
    def test_unknown_column(self):
        with pytest.raises(DataCleanError) as excinfo:
            normalize(frame(a=["1"]), "nope", "trim")
        assert excinfo.value.code == "unknown_column"

    def test_duplicate_column_in_step(self):
        config = NormalizeConfig(
            columns=[
                ColumnOps(column="a", operations=["trim"]),
                ColumnOps(column="a", operations=["lowercase"]),
            ]
        )
        with pytest.raises(DataCleanError) as excinfo:
            apply_normalization(frame(a=["X"]), config)
        assert excinfo.value.code == "duplicate_column_operation"
