import pandas as pd
import pytest

from app.core.dataframe_ops.validation_rules import apply_validation
from app.core.errors import DataCleanError
from app.schemas.validation import ValidateConfig, ValidationRule


def frame():
    return pd.DataFrame(
        {
            "mail": ["a@x.com", "bad", "", "c@x.com"],
            "age": ["30", "200", "", "abc"],
            "status": ["active", "inactive", "active", "bogus"],
            "code": ["AB12", "XY99", "nope", ""],
            "joined": ["2025-01-01", "2025-02-01", "junk-date", ""],
        }
    )


def run(rules: list[ValidationRule], drop=False):
    return apply_validation(frame(), ValidateConfig(rules=rules, drop_invalid_rows=drop))


class TestRules:
    def test_email_rule(self):
        results, _ = run([ValidationRule(column="mail", rule="email")])
        result = results[0]
        assert result.error_count == 1
        assert result.samples[0].value == "bad"
        assert result.samples[0].row == 2

    def test_required_rule_flags_empty(self):
        results, _ = run([ValidationRule(column="mail", rule="required")])
        assert results[0].error_count == 1  # only the "" cell

    def test_numeric_range(self):
        results, _ = run([ValidationRule(column="age", rule="numeric_range", min=0, max=120)])
        result = results[0]
        assert result.error_count == 2  # 200 out of range; abc not a number
        # Empty cells are the required rule's job, not the range rule's.
        reasons = {s.value: s.reason for s in result.samples}
        assert reasons["200"].startswith("value out of range")
        assert reasons["abc"] == "not a number"

    def test_string_length(self):
        results, _ = run([ValidationRule(column="code", rule="string_length", max_length=3)])
        assert results[0].error_count == 3
        assert results[0].samples[0].value == "AB12"

    def test_regex_fullmatch(self):
        results, _ = run([ValidationRule(column="code", rule="regex", pattern=r"[A-Z]{2}\d{2}")])
        assert results[0].error_count == 1
        assert results[0].samples[0].value == "nope"

    def test_allowed_values(self):
        results, _ = run(
            [ValidationRule(column="status", rule="allowed_values", values=["active", "inactive"])]
        )
        assert results[0].error_count == 1
        assert results[0].samples[0].value == "bogus"

    def test_date_rule(self):
        results, _ = run([ValidationRule(column="joined", rule="date")])
        assert results[0].error_count == 1
        assert results[0].samples[0].value == "junk-date"

    def test_range_without_bounds_rejected_by_schema(self):
        with pytest.raises(ValueError):
            ValidationRule(column="age", rule="numeric_range")

    def test_regex_without_pattern_rejected(self):
        with pytest.raises(ValueError):
            ValidationRule(column="code", rule="regex")

    def test_unknown_column_raises_clean_error(self):
        with pytest.raises(DataCleanError) as excinfo:
            run([ValidationRule(column="nope", rule="required")])
        assert excinfo.value.code == "unknown_column"

    def test_invalid_regex_rejected_at_runtime(self):
        with pytest.raises(DataCleanError) as excinfo:
            run([ValidationRule(column="code", rule="regex", pattern="([bad")])
        assert excinfo.value.code == "invalid_regex"

    def test_drop_invalid_rows_mask(self):
        _, mask = run(
            [
                ValidationRule(column="mail", rule="required"),
                ValidationRule(column="mail", rule="email"),
            ],
            drop=True,
        )
        # rows 2 ("bad") and 3 ("") fail
        assert mask.tolist() == [False, True, True, False]
