"""Filesystem storage for uploaded files, parsed datasets and exports.

Layout under DATA_CLEAN_DATA_DIR:
  uploads/<file_id>__<sanitized-name>   original upload bytes
  workspaces/<job_id>/original.pkl      dataset exactly as parsed
  workspaces/<job_id>/current.pkl       dataset after the last pipeline run
  exports/<job_id>/<filename>           generated export files
Raw data never goes into SQLite.
"""

from __future__ import annotations

import logging
import pickle
import shutil
from pathlib import Path

import pandas as pd

from app.config import get_settings

logger = logging.getLogger(__name__)


def workspace_dir(job_id: str) -> Path:
    return get_settings().workspace_dir / job_id


def original_path(job_id: str) -> Path:
    return workspace_dir(job_id) / "original.pkl"


def current_path(job_id: Path | str) -> Path:
    if isinstance(job_id, Path):
        return job_id / "current.pkl"
    return workspace_dir(job_id) / "current.pkl"


def save_original(job_id: str, df: pd.DataFrame) -> None:
    workspace_dir(job_id).mkdir(parents=True, exist_ok=True)
    _dump(original_path(job_id), df)
    _dump(current_path(job_id), df)


def save_current(job_id: str, df: pd.DataFrame) -> None:
    _dump(current_path(job_id), df)


def load_original(job_id: str) -> pd.DataFrame:
    return _load(original_path(job_id))


def load_current(job_id: str) -> pd.DataFrame:
    return _load(current_path(job_id))


def delete_workspace(job_id: str) -> None:
    shutil.rmtree(workspace_dir(job_id), ignore_errors=True)


def delete_exports(job_id: str) -> None:
    shutil.rmtree(get_settings().export_dir / job_id, ignore_errors=True)


def export_dir(job_id: str) -> Path:
    path = get_settings().export_dir / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dump(path: Path, df: pd.DataFrame) -> None:
    with path.open("wb") as handle:
        pickle.dump(df, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        from app.core.errors import DataCleanError

        raise DataCleanError(
            "dataset_missing",
            "The stored dataset for this job is missing (it may have been cleaned up).",
            status_code=410,
        )
    with path.open("rb") as handle:
        return pickle.load(handle)
