"""Provider registry: heuristic always available, OpenAI only with a key."""

from __future__ import annotations

from app.config import Settings
from app.core.errors import DataCleanError
from app.core.inference.base import SchemaInferenceProvider
from app.core.inference.heuristics import HeuristicInferenceProvider

HEURISTIC = "heuristic"
OPENAI = "openai"


def available_providers(settings: Settings) -> list[str]:
    providers = [HEURISTIC]
    if settings.openai_api_key:
        providers.append(OPENAI)
    return providers


def get_provider(name: str, settings: Settings) -> SchemaInferenceProvider:
    if name == HEURISTIC:
        return HeuristicInferenceProvider()
    if name == OPENAI:
        if not settings.openai_api_key:
            raise DataCleanError(
                "ai_provider_unavailable",
                "The OpenAI provider is not configured. Set OPENAI_API_KEY to"
                " enable it — or use the built-in heuristic mapping, which"
                " needs no key.",
                status_code=400,
                details={"provider": OPENAI},
            )
        from app.core.inference.openai_provider import OpenAIInferenceProvider

        return OpenAIInferenceProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    raise DataCleanError("unknown_provider", f"Unknown inference provider '{name}'.")
