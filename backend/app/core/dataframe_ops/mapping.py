"""Column mapping: rename, drop, reorder."""

from __future__ import annotations

import pandas as pd

from app.core.errors import DataCleanError
from app.schemas.transform import RenameConfig, StepSample


def apply_mapping(df: pd.DataFrame, config: RenameConfig) -> tuple[pd.DataFrame, dict]:
    for source in config.rename:
        if source not in df.columns:
            raise DataCleanError(
                "unknown_column",
                f"Cannot rename unknown column '{source}'.",
                details={"column": source},
            )
    for column in config.drop:
        if column not in df.columns:
            raise DataCleanError(
                "unknown_column",
                f"Cannot drop unknown column '{column}'.",
                details={"column": column},
            )

    conflicts = [
        new for new in config.rename.values() if new in df.columns and new not in config.rename
    ]
    if conflicts:
        raise DataCleanError(
            "column_name_conflict",
            f"Renaming would overwrite existing column(s): {', '.join(conflicts)}.",
            details={"columns": conflicts},
        )
    if len(set(config.rename.values())) != len(config.rename.values()):
        raise DataCleanError(
            "column_name_conflict",
            "Two columns cannot be renamed to the same target name.",
        )

    result = df.rename(columns=config.rename)
    result = result.drop(columns=[c for c in config.drop if c in result.columns])
    result = result.loc[:, ~result.columns.duplicated()]

    reordered = False
    if config.order:
        expected = sorted(result.columns)
        if sorted(config.order) != expected:
            raise DataCleanError(
                "invalid_column_order",
                f"'order' must be a permutation of the resulting columns {expected}.",
                details={"order": config.order},
            )
        result = result[config.order]
        reordered = True

    samples = [
        StepSample(row=0, column=old, before=old, after=new) for old, new in config.rename.items()
    ]
    stats = {
        "renamed": config.rename,
        "dropped": config.drop,
        "reordered": reordered,
        "output_columns": list(result.columns),
    }
    return result, {"stats": stats, "samples": samples, "removed_rows": []}
