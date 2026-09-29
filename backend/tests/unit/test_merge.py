import pandas as pd
import pytest

from app.core.dataframe_ops.merge import merge_frames
from app.core.errors import DataCleanError


def customers():
    return pd.DataFrame(
        {"cust_nm": ["Jo", "Al"], "mail": ["j@x.com", "a@x.com"], "city": ["Oslo", "Rome"]}
    )


def new_batch():
    return pd.DataFrame({"cust_nm": ["Bo"], "mail": ["b@x.com"], "region": ["north"]})


class TestUnionMerge:
    def test_union_columns_stable_order(self):
        merged, stats = merge_frames(
            [("j1", "a.csv", customers(), {}), ("j2", "b.csv", new_batch(), {})], "union"
        )
        assert list(merged.columns) == ["cust_nm", "mail", "city", "region"]
        assert len(merged) == 3
        assert stats["output_rows"] == 3
        assert stats["output_columns"] == 4

    def test_missing_columns_become_null(self):
        merged, stats = merge_frames(
            [("j1", "a.csv", customers(), {}), ("j2", "b.csv", new_batch(), {})], "union"
        )
        assert merged.at[2, "city"] is None
        assert merged.at[0, "region"] is None
        assert stats["null_cells_filled"] == 3  # 1 missing col * 2 rows + 2 missing * 1 row

    def test_three_files(self):
        third = pd.DataFrame({"cust_nm": ["Cy"], "notes": ["vip"]})
        merged, _ = merge_frames(
            [
                ("j1", "a.csv", customers(), {}),
                ("j2", "b.csv", new_batch(), {}),
                ("j3", "c.csv", third, {}),
            ],
            "union",
        )
        assert list(merged.columns) == ["cust_nm", "mail", "city", "region", "notes"]
        assert len(merged) == 4

    def test_mapping_aligns_columns(self):
        renamed = pd.DataFrame({"name": ["Bo"], "mail_address": ["b@x.com"]})
        merged, _ = merge_frames(
            [
                ("j1", "a.csv", customers(), {"mail": "email"}),
                ("j2", "b.csv", renamed, {"name": "customer_name", "mail_address": "email"}),
            ],
            "union",
        )
        assert list(merged.columns) == ["cust_nm", "email", "city", "customer_name"]
        assert merged.at[0, "email"] == "j@x.com"
        assert merged.at[1, "email"] == "a@x.com"
        assert merged.at[2, "email"] == "b@x.com"
        assert merged.at[2, "customer_name"] == "Bo"

    def test_mapping_unknown_column_rejected(self):
        with pytest.raises(DataCleanError) as excinfo:
            merge_frames([("j1", "a.csv", customers(), {"nope": "x"})], "union")
        assert excinfo.value.code == "unknown_column"


class TestIntersectionMerge:
    def test_shared_columns_only(self):
        merged, stats = merge_frames(
            [("j1", "a.csv", customers(), {}), ("j2", "b.csv", new_batch(), {})], "intersection"
        )
        assert list(merged.columns) == ["cust_nm", "mail"]
        assert len(merged) == 3
        assert stats["null_cells_filled"] == 0

    def test_no_common_columns(self):
        lonely = pd.DataFrame({"zzz": ["1"]})
        with pytest.raises(DataCleanError) as excinfo:
            merge_frames(
                [("j1", "a.csv", customers(), {}), ("j2", "b.csv", lonely, {})], "intersection"
            )
        assert excinfo.value.code == "no_common_columns"

    def test_invalid_mode(self):
        with pytest.raises(DataCleanError):
            merge_frames(
                [("j1", "a.csv", customers(), {}), ("j2", "b.csv", new_batch(), {})], "bogus"
            )
