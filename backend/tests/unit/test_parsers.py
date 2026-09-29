from pathlib import Path

import pytest

from app.core.dataframe_ops.parsers import load_dataframe
from app.core.errors import DataCleanError


class TestCsvParsing:
    def test_basic_csv(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"name,age\nJo,3\nAl,4\n")
        df = load_dataframe(path, "text")
        assert list(df.columns) == ["name", "age"]
        assert len(df) == 2
        assert df.at[0, "name"] == "Jo"
        assert df.at[0, "age"] == "3"

    def test_keeps_values_as_strings(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"zip,flag\n00121,true\n")
        df = load_dataframe(path, "text")
        assert df.at[0, "zip"] == "00121"  # leading zeros survive
        assert df.at[0, "flag"] == "true"

    def test_empty_cells_stay_empty_strings(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"a,b\n1,\n")
        df = load_dataframe(path, "text")
        assert df.at[0, "b"] == ""

    def test_utf8_bom(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes("naïve,age\nx,1\n".encode("utf-8-sig"))
        df = load_dataframe(path, "text")
        assert list(df.columns) == ["naïve", "age"]

    def test_cp1252_fallback(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"caf\xe9,age\nx,1\n")
        df = load_dataframe(path, "text")
        assert list(df.columns) == ["café", "age"]

    def test_invalid_encoding_rejected(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"a,b\n\xff\xfe\x00\x00,1\n")
        with pytest.raises(DataCleanError) as excinfo:
            load_dataframe(path, "text")
        assert excinfo.value.code == "invalid_encoding"

    def test_empty_file(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"")
        with pytest.raises(DataCleanError) as excinfo:
            load_dataframe(path, "text")
        assert excinfo.value.code == "empty_file"

    def test_whitespace_only_file(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"\n  \n")
        with pytest.raises(DataCleanError):
            load_dataframe(path, "text")

    def test_header_only_has_zero_rows(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"a,b\n")
        df = load_dataframe(path, "text")
        assert len(df) == 0
        assert list(df.columns) == ["a", "b"]

    def test_malformed_csv_row_lengths(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"a,b,c\n1,2,3\n4,5\n")
        with pytest.raises(DataCleanError) as excinfo:
            load_dataframe(path, "text")
        assert excinfo.value.code == "malformed_csv"

    def test_semicolon_delimiter_sniffed(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"name;age\nJo;3\n")
        df = load_dataframe(path, "text")
        assert list(df.columns) == ["name", "age"]

    def test_duplicate_column_names_deduplicated(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b"a,a\n1,2\n")
        df = load_dataframe(path, "text")
        assert list(df.columns) == ["a", "a_2"]

    def test_unnamed_column_gets_generated_name(self, tmp_path: Path):
        path = tmp_path / "t.csv"
        path.write_bytes(b",b\n1,2\n")
        df = load_dataframe(path, "text")
        assert list(df.columns) == ["column_1", "b"]


class TestExcelParsing:
    def test_xlsx_roundtrip(self, tmp_path: Path):
        import pandas as pd

        path = tmp_path / "t.xlsx"
        pd.DataFrame({"name": ["Jo"], "n": [42]}).to_excel(path, index=False)
        df = load_dataframe(path, "zip")
        assert list(df.columns) == ["name", "n"]
        assert df.at[0, "n"] == "42"  # no float artifact

    def test_xlsx_dates_formatted(self, tmp_path: Path):
        from datetime import datetime

        import pandas as pd

        path = tmp_path / "t.xlsx"
        pd.DataFrame({"d": [datetime(2025, 1, 15)]}).to_excel(path, index=False)
        df = load_dataframe(path, "zip")
        assert df.at[0, "d"] == "2025-01-15"

    def test_corrupt_xlsx(self, tmp_path: Path):
        path = tmp_path / "t.xlsx"
        path.write_bytes(b"PK\x03\x04not really a zip")
        with pytest.raises(DataCleanError) as excinfo:
            load_dataframe(path, "zip")
        assert excinfo.value.code == "malformed_xlsx"

    def test_xls_legacy(self):
        pytest.importorskip("xlrd")
        fixture = Path(__file__).parent.parent / "data" / "legacy_customers.xls"
        df = load_dataframe(fixture, "ole2")
        assert list(df.columns) == ["cust_nm", "ph_no", "n"]
        assert df.at[0, "ph_no"] == "555-0100"
        assert df.at[1, "n"] == "12"

    def test_unsupported_content_kind(self, tmp_path: Path):
        path = tmp_path / "t.bin"
        path.write_bytes(b"\x00\x01")
        with pytest.raises(DataCleanError):
            load_dataframe(path, "binary")
