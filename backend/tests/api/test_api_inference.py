import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes


@pytest.fixture()
def cryptic_job(client: TestClient) -> str:
    return upload_bytes(
        client,
        make_csv(
            "John Smith,john@example.com,+1 (555) 010-1234",
            "Jane Doe,jane@example.com,555-010-5678",
            header="cust_nm,mail,ph_no",
        ),
        "cryptic.csv",
    )["job_id"]


class TestInferenceEndpoints:
    def test_providers_without_key(self, client: TestClient, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from app.config import get_settings

        get_settings.cache_clear()
        body = client.get("/api/inference/providers").json()
        assert body["default"] == "heuristic"
        assert body["available"] == ["heuristic"]
        assert body["openai_configured"] is False
        get_settings.cache_clear()

    def test_providers_with_key(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
        from app.config import get_settings

        get_settings.cache_clear()
        body = client.get("/api/inference/providers").json()
        assert body["available"] == ["heuristic", "openai"]
        assert body["openai_configured"] is True
        get_settings.cache_clear()

    def test_heuristic_suggests_demo_mapping(self, client: TestClient, cryptic_job: str):
        body = client.post(
            f"/api/jobs/{cryptic_job}/infer-mapping",
            json={"provider": "heuristic"},
        ).json()
        mapping = {s["source"]: s["target"] for s in body["suggestions"]}
        assert mapping == {
            "cust_nm": "customer_name",
            "mail": "email",
            "ph_no": "phone",
        }
        assert all(0 <= s["confidence"] <= 1 for s in body["suggestions"])

    def test_default_targets_used_when_empty(self, client: TestClient, cryptic_job: str):
        body = client.post(
            f"/api/jobs/{cryptic_job}/infer-mapping", json={"target_schema": []}
        ).json()
        assert "customer_name" in body["targets_used"]

    def test_openai_without_key_clean_error(
        self, client: TestClient, cryptic_job: str, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from app.config import get_settings

        get_settings.cache_clear()
        response = client.post(
            f"/api/jobs/{cryptic_job}/infer-mapping", json={"provider": "openai"}
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ai_provider_unavailable"
        get_settings.cache_clear()

    def test_meta_exposes_inference_info(self, client: TestClient):
        meta = client.get("/api/meta").json()
        assert meta["inference"]["default"] == "heuristic"
        assert "customer_name" in meta["target_schema_suggestions"]
