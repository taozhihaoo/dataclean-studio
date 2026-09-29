import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes


@pytest.fixture()
def messy_job(client: TestClient) -> str:
    return upload_bytes(
        client,
        make_csv(
            "John,john@example.com,34",
            "Jane,broken-mail,28",
            "Bob,,99",
            "Nina,nina@example.com,150",
            header="name,mail,age",
        ),
        "messy.csv",
    )["job_id"]


class TestValidateEndpoint:
    def test_email_rule(self, client: TestClient, messy_job: str):
        response = client.post(
            f"/api/jobs/{messy_job}/validate",
            json={"rules": [{"column": "mail", "rule": "email"}]},
        )
        body = response.json()
        assert response.status_code == 200
        assert body["error_count_total"] == 1  # "" is the required rule's job
        assert body["passed"] is False
        rule = body["rules"][0]
        assert rule["error_count"] == 1
        assert rule["samples"][0]["value"] == "broken-mail"
        assert rule["samples"][0]["reason"]

    def test_numeric_range_rule(self, client: TestClient, messy_job: str):
        body = client.post(
            f"/api/jobs/{messy_job}/validate",
            json={"rules": [{"column": "age", "rule": "numeric_range", "min": 0, "max": 120}]},
        ).json()
        assert body["error_count_total"] == 1  # 150 out of range; "" is not counted

    def test_combined_rules(self, client: TestClient, messy_job: str):
        body = client.post(
            f"/api/jobs/{messy_job}/validate",
            json={
                "rules": [
                    {"column": "mail", "rule": "required"},
                    {"column": "mail", "rule": "email"},
                    {"column": "age", "rule": "numeric_range", "min": 0, "max": 120},
                ]
            },
        ).json()
        assert body["error_count_total"] == 3
        assert [r["passed"] for r in body["rules"]] == [False, False, False]

    def test_drop_invalid_rows_persists(self, client: TestClient, messy_job: str):
        body = client.post(
            f"/api/jobs/{messy_job}/validate",
            json={
                "drop_invalid_rows": True,
                "rules": [{"column": "mail", "rule": "email"}],
            },
        ).json()
        assert body["rows_dropped"] == 1
        assert body["output_rows"] == 3
        detail = client.get(f"/api/jobs/{messy_job}").json()
        assert detail["row_count"] == 3
        assert detail["is_transformed"] is True

    def test_unknown_rule_column(self, client: TestClient, messy_job: str):
        response = client.post(
            f"/api/jobs/{messy_job}/validate",
            json={"rules": [{"column": "nope", "rule": "required"}]},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unknown_column"

    def test_invalid_rule_body_rejected(self, client: TestClient, messy_job: str):
        response = client.post(
            f"/api/jobs/{messy_job}/validate",
            json={"rules": [{"column": "age", "rule": "numeric_range"}]},  # no bounds
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_unknown_rule_type_rejected(self, client: TestClient, messy_job: str):
        response = client.post(
            f"/api/jobs/{messy_job}/validate",
            json={"rules": [{"column": "age", "rule": "psychic"}]},
        )
        assert response.status_code == 422

    def test_empty_rules_rejected(self, client: TestClient, messy_job: str):
        assert client.post(f"/api/jobs/{messy_job}/validate", json={"rules": []}).status_code == 422
