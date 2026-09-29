import pandas as pd
import pytest

from app.core.errors import DataCleanError
from app.pipeline.engine import PipelineEngine
from app.schemas.transform import (
    ColumnOps,
    DedupeConfig,
    DedupeStep,
    NormalizeConfig,
    NormalizeStep,
    RenameConfig,
    RenameStep,
    ValidateConfig,
    ValidateStep,
)
from app.schemas.validation import ValidationRule


def frame():
    return pd.DataFrame(
        {
            "cust_nm": ["  John  ", "JANE", "John", "Bob"],
            "mail": ["john@x.com", "jane@x.com", "john@x.com", "bad"],
            "age": ["30", "40", "30", "999"],
        }
    )


def steps(*items):
    return items


class TestPipelineExecution:
    def test_full_order_normalize_dedupe_rename(self):
        engine = PipelineEngine(
            [
                NormalizeStep(
                    id="s1",
                    config=NormalizeConfig(
                        columns=[ColumnOps(column="cust_nm", operations=["trim", "title_case"])]
                    ),
                ),
                DedupeStep(id="s2", config=DedupeConfig(mode="exact", keep="first")),
                RenameStep(
                    id="s3",
                    config=RenameConfig(rename={"cust_nm": "customer_name"}),
                ),
            ]
        )
        outcome = engine.run(frame())
        assert outcome.input_rows == 4
        assert outcome.output_rows == 3
        assert list(outcome.df.columns) == ["customer_name", "mail", "age"]
        assert outcome.changed_cells > 0
        assert [s.step_id for s in outcome.steps] == ["s1", "s2", "s3"]

    def test_step_order_is_honored(self):
        """Rows that differ only by whitespace become duplicates after trim."""
        early = PipelineEngine(
            [
                DedupeStep(id="d", config=DedupeConfig(mode="exact", keep="first")),
                NormalizeStep(
                    id="n",
                    config=NormalizeConfig(
                        columns=[ColumnOps(column="cust_nm", operations=["trim"])]
                    ),
                ),
            ]
        ).run(frame())
        late = PipelineEngine(
            [
                NormalizeStep(
                    id="n",
                    config=NormalizeConfig(
                        columns=[ColumnOps(column="cust_nm", operations=["trim"])]
                    ),
                ),
                DedupeStep(id="d", config=DedupeConfig(mode="exact", keep="first")),
            ]
        ).run(frame())
        assert early.output_rows == 4  # raw rows are not exact duplicates
        assert late.output_rows == 3  # trim unifies them, dedupe removes one

    def test_disabled_step_is_skipped(self):
        outcome = PipelineEngine(
            [
                NormalizeStep(
                    id="n",
                    enabled=False,
                    config=NormalizeConfig(
                        columns=[ColumnOps(column="cust_nm", operations=["trim"])]
                    ),
                ),
                DedupeStep(id="d", config=DedupeConfig(mode="exact", keep="first")),
            ]
        ).run(frame())
        assert outcome.steps[0].status == "skipped"
        # raw rows differ (whitespace), so exact dedupe removes nothing
        assert outcome.output_rows == 4

    def test_validate_step_reports_and_drops(self):
        outcome = PipelineEngine(
            [
                ValidateStep(
                    id="v",
                    config=ValidateConfig(
                        rules=[ValidationRule(column="age", rule="numeric_range", min=0, max=120)],
                        drop_invalid_rows=True,
                    ),
                )
            ]
        ).run(frame())
        assert outcome.output_rows == 3
        assert outcome.validation_results[0].error_count == 1
        assert outcome.steps[0].stats["rows_dropped"] == 1

    def test_validate_without_drop_keeps_rows(self):
        outcome = PipelineEngine(
            [
                ValidateStep(
                    id="v",
                    config=ValidateConfig(
                        rules=[ValidationRule(column="age", rule="numeric_range", min=0, max=120)]
                    ),
                )
            ]
        ).run(frame())
        assert outcome.output_rows == 4
        assert outcome.steps[0].stats["rows_dropped"] == 0

    def test_normalize_samples_show_before_after(self):
        outcome = PipelineEngine(
            [
                NormalizeStep(
                    id="n",
                    config=NormalizeConfig(
                        columns=[ColumnOps(column="cust_nm", operations=["trim"])]
                    ),
                )
            ]
        ).run(frame())
        samples = outcome.steps[0].samples
        assert samples[0].before == "  John  "
        assert samples[0].after == "John"

    def test_dedupe_removed_rows(self):
        exact_dup = pd.DataFrame(
            {
                "cust_nm": ["John", "Jane", "John"],
                "mail": ["john@x.com", "jane@x.com", "john@x.com"],
            }
        )
        outcome = PipelineEngine(
            [DedupeStep(id="d", config=DedupeConfig(mode="exact", keep="first"))]
        ).run(exact_dup)
        assert outcome.output_rows == 2
        assert len(outcome.steps[0].removed_rows) == 1
        assert outcome.steps[0].removed_rows[0]["mail"] == "john@x.com"

    def test_rename_samples(self):
        outcome = PipelineEngine(
            [RenameStep(id="r", config=RenameConfig(rename={"mail": "email"}))]
        ).run(frame())
        assert outcome.steps[0].samples[0].before == "mail"
        assert outcome.steps[0].samples[0].after == "email"


class TestPipelineErrors:
    def test_duplicate_step_ids_rejected(self):
        step = RenameStep(id="same", config=RenameConfig())
        with pytest.raises(DataCleanError) as excinfo:
            PipelineEngine([step, step])
        assert excinfo.value.code == "duplicate_pipeline_step"

    def test_step_error_carries_step_context(self):
        engine = PipelineEngine([RenameStep(id="r", config=RenameConfig(rename={"missing": "x"}))])
        with pytest.raises(DataCleanError) as excinfo:
            engine.run(frame())
        assert excinfo.value.details["step_id"] == "r"
        assert excinfo.value.details["step_type"] == "rename"

    def test_engine_does_not_mutate_input(self):
        df = frame()
        PipelineEngine(
            [
                NormalizeStep(
                    id="n",
                    config=NormalizeConfig(
                        columns=[ColumnOps(column="cust_nm", operations=["trim"])]
                    ),
                )
            ]
        ).run(df)
        assert df.at[0, "cust_nm"] == "  John  "

    def test_changed_cells_counted_only_when_shape_stable(self):
        outcome = PipelineEngine(
            [DedupeStep(id="d", config=DedupeConfig(mode="exact", keep="first"))]
        ).run(frame())
        assert outcome.changed_cells == 0
