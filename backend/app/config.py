"""Application settings loaded from environment variables.

Everything has a safe local default: the app runs fully offline with no
API keys. The only optional key is OPENAI_API_KEY, which enables the
optional AI schema-inference provider (see app/core/inference).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app import __version__

NULL_TOKENS = ["null", "n/a", "na", "none", "nan", "-"]


class Settings:
    """Runtime settings with local-first defaults."""

    def __init__(self) -> None:
        self.version = __version__
        self.app_name = "DataClean Studio"

        self.data_dir = Path(os.environ.get("DATA_CLEAN_DATA_DIR", "data"))
        self.max_upload_mb = max(1, int(os.environ.get("DATA_CLEAN_MAX_UPLOAD_MB", "25")))
        self.preview_row_limit = 50
        self.max_preview_rows = 200

        # Optional AI schema inference. None => only the deterministic
        # heuristic provider is available. No core feature depends on this.
        self.openai_api_key: str | None = os.environ.get("OPENAI_API_KEY") or None
        self.openai_model = os.environ.get("DATA_CLEAN_OPENAI_MODEL", "gpt-4o-mini")
        self.openai_base_url = os.environ.get(
            "DATA_CLEAN_OPENAI_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self.openai_timeout_seconds = float(os.environ.get("DATA_CLEAN_OPENAI_TIMEOUT", "20"))

        self.upload_dir = self.data_dir / "uploads"
        self.workspace_dir = self.data_dir / "workspaces"
        self.export_dir = self.data_dir / "exports"
        self.db_path = self.data_dir / "dataclean.db"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        for directory in (self.data_dir, self.upload_dir, self.workspace_dir, self.export_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
