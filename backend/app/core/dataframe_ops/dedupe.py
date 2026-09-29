"""Duplicate detection: exact-row duplicates or key-column duplicates."""

from __future__ import annotations

import pandas as pd

from app.core.dataframe_ops.parsers import dataframe_to_records
from app.core.errors import DataCleanError
from app.schemas.transform import DedupeConfig

_MAX_REMOVED_SAMPLES = 5


def deduplicate(df: pd.DataFrame, config: DedupeConfig) -> tuple[pd.DataFrame, dict]:
    if config.mode == "columns":
        if not config.columns:
            raise DataCleanError(
                "invalid_pipeline",
                "Column-based deduplication requires at least one key column.",
            )
        missing = [c for c in config.columns if c not in df.columns]
        if missing:
            raise DataCleanError(
                "unknown_column",
                f"Deduplication key column(s) not found: {', '.join(missing)}.",
                details={"columns": missing},
            )
        subset = config.columns
    else:
        subset = None

    involved = df.duplicated(subset=subset, keep=False)
    duplicates_removed = df.duplicated(subset=subset, keep=config.keep)
    removed_rows = df[duplicates_removed]
    result = df[~duplicates_removed]

    stats = {
        "mode": config.mode,
        "key_columns": subset or [],
        "keep": config.keep,
        "duplicate_rows_involved": int(involved.sum()),
        "rows_removed": int(duplicates_removed.sum()),
        "output_rows": int(len(result)),
    }
    samples = dataframe_to_records(removed_rows.head(_MAX_REMOVED_SAMPLES))
    return result, {"stats": stats, "samples": [], "removed_rows": samples}
