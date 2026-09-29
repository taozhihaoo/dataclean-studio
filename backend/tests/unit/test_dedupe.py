import pandas as pd
import pytest

from app.core.dataframe_ops.dedupe import deduplicate
from app.core.errors import DataCleanError
from app.schemas.transform import DedupeConfig


def frame():
    return pd.DataFrame(
        {
            "mail": ["a@x.com", "b@x.com", "a@x.com", "c@x.com", "b@x.com"],
            "name": ["A", "B", "A", "C", "B"],
        }
    )


class TestExactDedupe:
    def test_keep_first(self):
        result, payload = deduplicate(frame(), DedupeConfig(mode="exact", keep="first"))
        assert len(result) == 3
        assert payload["stats"]["rows_removed"] == 2
        assert payload["stats"]["duplicate_rows_involved"] == 4
        assert payload["stats"]["output_rows"] == 3

    def test_keep_last(self):
        result, _ = deduplicate(frame(), DedupeConfig(mode="exact", keep="last"))
        assert len(result) == 3
        assert result["name"].tolist() == ["A", "C", "B"]

    def test_removed_row_samples(self):
        _, payload = deduplicate(frame(), DedupeConfig(mode="exact", keep="first"))
        assert len(payload["removed_rows"]) == 2
        assert payload["removed_rows"][0]["mail"] == "a@x.com"

    def test_empty_frame(self):
        empty = pd.DataFrame({"a": pd.Series([], dtype=object)})
        result, payload = deduplicate(empty, DedupeConfig())
        assert len(result) == 0
        assert payload["stats"]["rows_removed"] == 0


class TestColumnDedupe:
    def test_key_column(self):
        result, payload = deduplicate(
            frame(), DedupeConfig(mode="columns", columns=["mail"], keep="first")
        )
        assert len(result) == 3
        assert payload["stats"]["key_columns"] == ["mail"]

    def test_composite_key(self):
        df = pd.DataFrame({"a": ["1", "1", "2"], "b": ["x", "y", "x"], "c": ["p", "q", "r"]})
        result, payload = deduplicate(
            df, DedupeConfig(mode="columns", columns=["a", "b"], keep="first")
        )
        assert len(result) == 3
        assert payload["stats"]["rows_removed"] == 0

    def test_missing_key_column(self):
        with pytest.raises(DataCleanError) as excinfo:
            deduplicate(frame(), DedupeConfig(mode="columns", columns=["nope"]))
        assert excinfo.value.code == "unknown_column"

    def test_columns_mode_requires_keys(self):
        with pytest.raises(DataCleanError) as excinfo:
            deduplicate(frame(), DedupeConfig(mode="columns", columns=[]))
        assert excinfo.value.code == "invalid_pipeline"
