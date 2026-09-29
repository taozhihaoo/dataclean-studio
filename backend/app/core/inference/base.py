"""Schema inference provider abstraction.

DataClean Studio never depends on an AI provider: the deterministic
heuristic provider is always available and is the default. An external
provider is strictly opt-in (needs a key and an explicit user action).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ColumnSample:
    """Minimal, explicitly shared column information (never a full file)."""

    name: str
    sample_values: list[str] = field(default_factory=list)


@dataclass
class MappingSuggestion:
    source: str
    target: str
    confidence: float
    rationale: str
    provider: str


class SchemaInferenceProvider(Protocol):
    name: str

    def suggest(self, columns: list[ColumnSample], targets: list[str]) -> list[MappingSuggestion]:
        """Return suggested source->target mappings. Must never raise for
        "no suggestion"; raise DataCleanError only for provider failures."""
