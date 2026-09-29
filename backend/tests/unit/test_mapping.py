import pandas as pd
import pytest

from app.core.dataframe_ops.mapping import apply_mapping
from app.core.errors import DataCleanError
from app.schemas.transform import RenameConfig


def frame():
    return pd.DataFrame({"cust_nm": ["Jo"], "mail": ["a@x.com"], "ph_no": ["555"], "extra": ["x"]})


class TestRename:
    def test_rename_columns(self):
        result, payload = apply_mapping(frame(), RenameConfig(rename={"cust_nm": "customer_name"}))
        assert "customer_name" in result.columns
        assert "cust_nm" not in result.columns
        assert payload["stats"]["renamed"] == {"cust_nm": "customer_name"}

    def test_rename_samples(self):
        _, payload = apply_mapping(frame(), RenameConfig(rename={"mail": "email"}))
        assert payload["samples"][0].before == "mail"
        assert payload["samples"][0].after == "email"

    def test_drop_columns(self):
        result, _ = apply_mapping(frame(), RenameConfig(drop=["extra", "ph_no"]))
        assert list(result.columns) == ["cust_nm", "mail"]

    def test_reorder(self):
        result, payload = apply_mapping(
            frame(), RenameConfig(order=["mail", "cust_nm", "ph_no", "extra"])
        )
        assert list(result.columns) == ["mail", "cust_nm", "ph_no", "extra"]
        assert payload["stats"]["reordered"] is True

    def test_full_clean_mapping_chain(self):
        result, _ = apply_mapping(
            frame(),
            RenameConfig(
                rename={"cust_nm": "customer_name", "mail": "email", "ph_no": "phone"},
                drop=["extra"],
                order=["customer_name", "email", "phone"],
            ),
        )
        assert list(result.columns) == ["customer_name", "email", "phone"]


class TestMappingErrors:
    def test_unknown_rename_source(self):
        with pytest.raises(DataCleanError) as excinfo:
            apply_mapping(frame(), RenameConfig(rename={"nope": "x"}))
        assert excinfo.value.code == "unknown_column"

    def test_unknown_drop_column(self):
        with pytest.raises(DataCleanError) as excinfo:
            apply_mapping(frame(), RenameConfig(drop=["nope"]))
        assert excinfo.value.code == "unknown_column"

    def test_rename_collision(self):
        with pytest.raises(DataCleanError) as excinfo:
            apply_mapping(frame(), RenameConfig(rename={"cust_nm": "mail"}))
        assert excinfo.value.code == "column_name_conflict"

    def test_rename_to_same_target(self):
        with pytest.raises(DataCleanError) as excinfo:
            apply_mapping(frame(), RenameConfig(rename={"cust_nm": "x", "mail": "x"}))
        assert excinfo.value.code == "column_name_conflict"

    def test_invalid_order(self):
        with pytest.raises(DataCleanError) as excinfo:
            apply_mapping(frame(), RenameConfig(order=["mail"]))
        assert excinfo.value.code == "invalid_column_order"
