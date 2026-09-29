"""Dataset merge (vertical stack with schema reconciliation)."""

from __future__ import annotations

import pandas as pd

from app.core.dataframe_ops.profile import is_null
from app.core.errors import DataCleanError


def merge_frames(
    frames: list[tuple[str, str, pd.DataFrame, dict[str, str]]], mode: str
) -> tuple[pd.DataFrame, dict]:
    """Stack datasets; each entry is (job_id, filename, df, column_mapping).

    ``mapping`` renames that dataset's columns before merging, which lets
    heterogeneous sources line up (cust_nm -> customer_name).
    """
    mapped: list[tuple[str, str, pd.DataFrame]] = []
    for job_id, filename, df, mapping in frames:
        unknown = [c for c in mapping if c not in df.columns]
        if unknown:
            raise DataCleanError(
                "unknown_column",
                f"Column mapping for '{filename}' targets unknown column(s): {', '.join(unknown)}.",
                details={"columns": unknown},
            )
        mapped.append((job_id, filename, df.rename(columns=mapping)))

    if mode == "union":
        columns: list[str] = []
        for _, _, df in mapped:
            for column in df.columns:
                if column not in columns:
                    columns.append(column)
    elif mode == "intersection":
        shared = set(mapped[0][2].columns)
        for _, _, df in mapped[1:]:
            shared &= set(df.columns)
        columns = [c for c in mapped[0][2].columns if c in shared]
        if not columns:
            raise DataCleanError(
                "no_common_columns",
                "The selected datasets have no columns in common; try union mode.",
            )
    else:
        raise DataCleanError("invalid_merge_mode", f"Unknown merge mode '{mode}'.")

    # Missing columns are filled with None: in the canonical model None is
    # the null value, and the preview renders it explicitly as "no value".
    aligned = []
    for _job_id, _filename, df in mapped:
        out = pd.DataFrame(index=df.index)
        for column in columns:
            out[column] = df[column] if column in df.columns else None
        aligned.append(out)
    merged = pd.concat(aligned, ignore_index=True)
    merged.columns = [str(c) for c in merged.columns]

    null_cells_filled = sum(max(0, len(columns) - len(df.columns)) * len(df) for _, _, df in mapped)
    file_stats = [
        {
            "job_id": job_id,
            "filename": filename,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
        }
        for job_id, filename, df, _mapping in frames
    ]
    stats = {
        "mode": mode,
        "input_files": file_stats,
        "output_rows": int(len(merged)),
        "output_columns": len(columns),
        "columns": columns,
        "null_cells_filled": int(null_cells_filled),
    }
    return merged, stats


def count_null_cells(df: pd.DataFrame) -> int:
    return int(sum(df[column].map(is_null).sum() for column in df.columns))
