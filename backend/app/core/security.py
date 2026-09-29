"""Security helpers: filename sanitizing, content sniffing, and
spreadsheet formula-injection protection for CSV/XLSX exports.

Exported files are opened in Excel by end users, so any cell whose text
could be interpreted as a formula (=SUM(A1), +CMD|' /C calc'!A0, @x, ...)
is neutralized by prefixing a single quote. Values that are plainly signed
numbers ("-5", "+3.5") are left untouched.
"""

from __future__ import annotations

import os
import re

from app.core.errors import DataCleanError

MAX_FILENAME_LEN = 100
MAX_REGEX_PATTERN_LEN = 200

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_SIGNED_NUMBER = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_FORMULA_START = re.compile(r"^[=+\-@\t\r]")


def sanitize_filename(name: str) -> str:
    """Reduce a client-supplied filename to a safe basename.

    The stored file never uses this name directly (we store by generated id);
    this only keeps a readable, safe copy for display and export naming.
    """
    base = os.path.basename(name.replace("\\", "/")).strip()
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", base).lstrip("._")
    cleaned = cleaned[:MAX_FILENAME_LEN].rstrip(". ")
    return cleaned or "upload"


def sniff_content_kind(head: bytes) -> str:
    """Classify raw bytes as 'zip', 'ole2', 'text' or 'binary'.

    We never trust the client-declared MIME type; uploads are routed by
    this sniff plus the (sanitized) filename extension.
    """
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return "zip"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole2"
    if looks_textual(head):
        return "text"
    return "binary"


_CONTROL_BYTES = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def looks_textual(data: bytes) -> bool:
    """Heuristic: binary control bytes (excluding \\t \\n \\r) mean not text."""
    sample = data[:8192]
    return not _CONTROL_BYTES.search(sample)


def is_dangerous_formula(value: str) -> bool:
    """True when a string value could execute as a spreadsheet formula."""
    if not value:
        return False
    if _SIGNED_NUMBER.match(value):
        return False
    return bool(_FORMULA_START.match(value))


def sanitize_formula_value(value: str) -> str:
    """Neutralize formula-like strings with a leading single quote."""
    if is_dangerous_formula(value):
        return "'" + value
    return value


def compile_user_regex(pattern: str) -> re.Pattern[str]:
    """Compile a user-supplied regex with a length cap.

    Note: this prevents trivial abuse (very long patterns) but Python's re
    has no backtracking limit, so pathological patterns can still be slow.
    Documented in the README under Limitations/Security.
    """
    if len(pattern) > MAX_REGEX_PATTERN_LEN:
        raise DataCleanError(
            "invalid_regex",
            f"Regex pattern is too long (max {MAX_REGEX_PATTERN_LEN} characters).",
        )
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise DataCleanError(
            "invalid_regex",
            f"Invalid regular expression: {exc}",
        ) from exc
