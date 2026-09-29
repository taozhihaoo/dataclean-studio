import pytest

from app.core.errors import DataCleanError
from app.core.security import (
    compile_user_regex,
    is_dangerous_formula,
    sanitize_filename,
    sanitize_formula_value,
    sniff_content_kind,
)


class TestSanitizeFilename:
    def test_plain_name_unchanged(self):
        assert sanitize_filename("report.csv") == "report.csv"

    def test_strips_path_traversal(self):
        assert sanitize_filename("../../etc/passwd") == "passwd"
        assert sanitize_filename("..\\..\\windows\\system32\\evil.csv") == "evil.csv"

    def test_strips_leading_dots(self):
        assert sanitize_filename("..hidden.csv") == "hidden.csv"

    def test_replaces_unsafe_characters(self):
        assert sanitize_filename("my file*name?.csv") == "my_file_name_.csv"

    def test_empty_becomes_upload(self):
        assert sanitize_filename("") == "upload"
        assert sanitize_filename("...") == "upload"

    def test_truncates_long_names(self):
        assert len(sanitize_filename("x" * 500 + ".csv")) <= 100


class TestContentSniffing:
    def test_zip_magic(self):
        assert sniff_content_kind(b"PK\x03\x04whatever") == "zip"

    def test_ole2_magic(self):
        assert sniff_content_kind(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1data") == "ole2"

    def test_text(self):
        assert sniff_content_kind(b"name,age\nJo,3\n") == "text"

    def test_binary(self):
        assert sniff_content_kind(b"\x00\x01\x02\x03binaryjunk") == "binary"


class TestFormulaGuard:
    @pytest.mark.parametrize(
        "value",
        ["=SUM(A1:A2)", "+CMD|' /C calc'!A0", "@import", "=1+1", "\tcmd", "-CMD()"],
    )
    def test_dangerous_values(self, value):
        assert is_dangerous_formula(value)

    @pytest.mark.parametrize("value", ["-5", "+3.5", "hello", "3=3", "", "a=b"])
    def test_safe_values(self, value):
        assert not is_dangerous_formula(value)

    def test_sanitize_prefixes_quote(self):
        assert sanitize_formula_value("=SUM(A1)") == "'=SUM(A1)"

    def test_sanitize_keeps_plain_numbers(self):
        assert sanitize_formula_value("-5") == "-5"


class TestUserRegex:
    def test_valid_pattern_compiles(self):
        assert compile_user_regex(r"^\d{4}$")

    def test_invalid_pattern_raises_clean_error(self):
        with pytest.raises(DataCleanError) as excinfo:
            compile_user_regex("([unclosed")
        assert excinfo.value.code == "invalid_regex"

    def test_overlong_pattern_rejected(self):
        with pytest.raises(DataCleanError):
            compile_user_regex("a" * 500)
