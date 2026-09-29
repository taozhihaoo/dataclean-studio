import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes

PIPELINE = {
    "steps": [
        {
            "id": "norm",
            "type": "normalize",
            "config": {
                "columns": [
                    {"column": "cust_nm", "operations": ["trim", "title_case"]},
                    {"column": "mail", "operations": ["empty_to_null", "lowercase"]},
                ]
            },
        },
        {
            "id": "dedupe",
            "type": "dedupe",
            "config": {"mode": "columns", "columns": ["mail"], "keep": "first"},
        },
        {
            "id": "rename",
            "type": "rename",
            "config": {"rename": {"cust_nm": "customer_name", "mail": "email"}},
        },
    ]
}


@pytest.fixture()
def dirty_job(client: TestClient) -> str:
    return upload_bytes(
        client,
        make_csv(
            "  john smith  ,JOHN@Example.com,34",
            "jane doe,jane@example.com,28",
            "  john smith  ,JOHN@Example.com,34",  # dup after trim+lowercase
            "empty mail,,44",
            header="cust_nm,mail,age",
        ),
        "dirty.csv",
    )["job_id"]


class TestTransformEndpoint:
    def test_pipeline_execution_and_persistence(self, client: TestClient, dirty_job: str):
        body = client.post(f"/api/jobs/{dirty_job}/transform", json=PIPELINE).json()
        assert body["input_rows"] == 4
        assert body["output_rows"] == 3  # one duplicate removed
        assert body["columns"] == ["customer_name", "email", "age"]
        assert body["changed_cells"] > 0
        assert [s["status"] for s in body["steps"]] == ["applied", "applied", "applied"]

        detail = client.get(f"/api/jobs/{dirty_job}").json()
        assert detail["is_transformed"] is True
        assert detail["row_count"] == 3
        assert [c["name"] for c in detail["columns"]] == ["customer_name", "email", "age"]

        preview = client.get(f"/api/jobs/{dirty_job}/preview").json()
        assert list(preview["rows"][0]) == ["customer_name", "email", "age"]
        assert preview["rows"][0]["customer_name"] == "John Smith"

    def test_step_reports_contain_stats_and_samples(self, client: TestClient, dirty_job: str):
        body = client.post(f"/api/jobs/{dirty_job}/transform", json=PIPELINE).json()
        normalize_step = body["steps"][0]
        assert normalize_step["stats"]["changed_cells"] > 0
        assert normalize_step["samples"]
        dedupe_step = body["steps"][1]
        assert dedupe_step["stats"]["rows_removed"] == 1
        assert dedupe_step["removed_rows"]
        rename_step = body["steps"][2]
        assert rename_step["stats"]["renamed"] == {"cust_nm": "customer_name", "mail": "email"}

    def test_rerun_pipeline_starts_from_original(self, client: TestClient, dirty_job: str):
        client.post(f"/api/jobs/{dirty_job}/transform", json=PIPELINE)
        # Run a pipeline with no dedupe: still 4 rows, proving no compounding.
        single = {
            "steps": [
                {
                    "id": "only-normalize",
                    "type": "normalize",
                    "config": {"columns": [{"column": "cust_nm", "operations": ["trim"]}]},
                }
            ]
        }
        body = client.post(f"/api/jobs/{dirty_job}/transform", json=single).json()
        assert body["output_rows"] == 4

    def test_preview_does_not_persist(self, client: TestClient, dirty_job: str):
        body = client.post(f"/api/jobs/{dirty_job}/transform/preview", json=PIPELINE).json()
        assert body["output_rows"] == 3
        detail = client.get(f"/api/jobs/{dirty_job}").json()
        assert detail["is_transformed"] is False
        assert detail["row_count"] == 4

    def test_disabled_step_skipped(self, client: TestClient, dirty_job: str):
        pipeline = {
            "steps": [
                {"id": "dedupe", "type": "dedupe", "enabled": False, "config": {"mode": "exact"}},
            ]
        }
        body = client.post(f"/api/jobs/{dirty_job}/transform", json=pipeline).json()
        assert body["steps"][0]["status"] == "skipped"
        assert body["output_rows"] == 4

    def test_unknown_column_in_step(self, client: TestClient, dirty_job: str):
        pipeline = {
            "steps": [
                {
                    "id": "bad",
                    "type": "normalize",
                    "config": {"columns": [{"column": "ghost", "operations": ["trim"]}]},
                }
            ]
        }
        response = client.post(f"/api/jobs/{dirty_job}/transform", json=pipeline)
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "unknown_column"
        assert error["details"]["step_id"] == "bad"

    def test_duplicate_step_ids_rejected(self, client: TestClient, dirty_job: str):
        pipeline = {
            "steps": [
                {"id": "same", "type": "dedupe", "config": {"mode": "exact"}},
                {"id": "same", "type": "dedupe", "config": {"mode": "exact"}},
            ]
        }
        response = client.post(f"/api/jobs/{dirty_job}/transform", json=pipeline)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "duplicate_pipeline_step"

    def test_unknown_step_type_rejected_with_clean_422(self, client: TestClient, dirty_job: str):
        pipeline = {"steps": [{"id": "x", "type": "teleport", "config": {}}]}
        response = client.post(f"/api/jobs/{dirty_job}/transform", json=pipeline)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_empty_pipeline_rejected(self, client: TestClient, dirty_job: str):
        assert (
            client.post(f"/api/jobs/{dirty_job}/transform", json={"steps": []}).status_code == 422
        )

    def test_job_not_found(self, client: TestClient):
        response = client.post(
            "/api/jobs/nope-not-here-1/transform",
            json={"steps": [{"id": "d", "type": "dedupe", "config": {"mode": "exact"}}]},
        )
        assert response.status_code == 404
