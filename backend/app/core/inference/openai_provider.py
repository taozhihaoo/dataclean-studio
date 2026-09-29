"""Optional OpenAI-backed schema inference.

This provider is only constructed when OPENAI_API_KEY is configured. It
sends **column names plus up to 3 sample values per column** — never the
full file — and only when the user explicitly triggers AI inference in the
UI. Tests never touch this module's network path (the transport is
injected and replaced with fakes).
"""

from __future__ import annotations

import json
import logging

import httpx

from app.core.errors import DataCleanError
from app.core.inference.base import ColumnSample, MappingSuggestion

logger = logging.getLogger(__name__)

_MAX_SAMPLE_VALUES = 3
_SYSTEM_PROMPT = (
    "You map messy source column names to a target schema. Reply with ONLY a"
    ' JSON array of objects: {"source": str, "target": str,'
    ' "confidence": float, "rationale": str}. Only map columns you are'
    " reasonably sure about. Do not invent target fields outside the"
    " provided target schema."
)


class OpenAIInferenceProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def suggest(self, columns: list[ColumnSample], targets: list[str]) -> list[MappingSuggestion]:
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "columns": [
                                {
                                    "name": c.name,
                                    "sample_values": c.sample_values[:_MAX_SAMPLE_VALUES],
                                }
                                for c in columns
                            ],
                            "target_schema": targets,
                        }
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._client.post(f"{self._base_url}/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            raw = json.loads(content)
            items = raw.get("suggestions", raw) if isinstance(raw, dict) else raw
            return self._parse(items)
        except DataCleanError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("OpenAI inference failed: %s", exc)
            raise DataCleanError(
                "ai_provider_error",
                "The AI provider could not be reached or returned an unusable"
                " response. The heuristic mapping remains available.",
            ) from exc

    def _parse(self, items: object) -> list[MappingSuggestion]:
        suggestions: list[MappingSuggestion] = []
        if not isinstance(items, list):
            return suggestions
        for item in items:
            try:
                suggestions.append(
                    MappingSuggestion(
                        source=str(item["source"]),
                        target=str(item["target"]),
                        confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                        rationale=str(item.get("rationale", "AI suggestion")),
                        provider=self.name,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return suggestions
