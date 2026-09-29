"""OpenAI provider tests use a fake transport — no network, no real API."""

import json

import httpx
import pytest

from app.core.errors import DataCleanError
from app.core.inference.base import ColumnSample
from app.core.inference.openai_provider import OpenAIInferenceProvider
from app.core.inference.registry import get_provider


def make_provider(handler) -> OpenAIInferenceProvider:
    transport = httpx.MockTransport(handler)
    return OpenAIInferenceProvider(
        api_key="test-key-not-real",
        model="test-model",
        base_url="https://example.invalid/v1",
        timeout_seconds=5,
        transport=transport,
    )


def ai_payload(suggestions: list[dict]) -> httpx.Response:
    content = json.dumps({"suggestions": suggestions})
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "https://example.invalid/v1/chat/completions"),
    )


COLUMNS = [ColumnSample(name="cust_nm", sample_values=["John"]), ColumnSample(name="mail")]


class TestOpenAIProvider:
    def test_parses_suggestions(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "test-model"
            assert body["messages"][1]["content"]
            return ai_payload(
                [
                    {
                        "source": "cust_nm",
                        "target": "customer_name",
                        "confidence": 0.92,
                        "rationale": "obvious",
                    },
                    {
                        "source": "mail",
                        "target": "email",
                        "confidence": 0.97,
                        "rationale": "obvious",
                    },
                ]
            )

        provider = make_provider(handler)
        suggestions = provider.suggest(COLUMNS, ["customer_name", "email"])
        assert [(s.source, s.target) for s in suggestions] == [
            ("cust_nm", "customer_name"),
            ("mail", "email"),
        ]
        assert all(s.provider == "openai" for s in suggestions)

    def test_confidence_clamped(self):
        provider = make_provider(
            lambda _: ai_payload([{"source": "a", "target": "b", "confidence": 5}])
        )
        suggestions = provider.suggest(COLUMNS, ["b"])
        assert suggestions[0].confidence == 1.0

    def test_malformed_items_skipped(self):
        provider = make_provider(
            lambda _: ai_payload([{"nope": True}, "garbage", {"source": "a", "target": "b"}])
        )
        suggestions = provider.suggest(COLUMNS, ["b"])
        assert len(suggestions) == 1

    def test_http_error_raises_clean_ai_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom", request=request)

        provider = make_provider(handler)
        with pytest.raises(DataCleanError) as excinfo:
            provider.suggest(COLUMNS, ["email"])
        assert excinfo.value.code == "ai_provider_error"

    def test_invalid_json_raises_clean_ai_error(self):
        provider = make_provider(
            lambda _: httpx.Response(
                200,
                json={"choices": [{"message": {"content": "not json"}}]},
                request=httpx.Request("POST", "https://x"),
            )
        )
        with pytest.raises(DataCleanError):
            provider.suggest(COLUMNS, ["email"])


class TestRegistry:
    def test_openai_requires_key(self, monkeypatch):
        from app.config import Settings

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(DataCleanError) as excinfo:
            get_provider("openai", Settings())
        assert excinfo.value.code == "ai_provider_unavailable"

    def test_unknown_provider(self):
        from app.config import Settings

        with pytest.raises(DataCleanError):
            get_provider("skynet", Settings())

    def test_heuristic_always_available(self):
        from app.config import Settings

        provider = get_provider("heuristic", Settings())
        assert provider.name == "heuristic"
