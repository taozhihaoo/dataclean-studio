"""Domain errors.

Every user-facing failure is raised as a DataCleanError carrying a stable
machine-readable code, a safe message, and an HTTP status. Unexpected
exceptions never leak tracebacks to clients (see app/api/error_handlers).
"""

from __future__ import annotations


class DataCleanError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
