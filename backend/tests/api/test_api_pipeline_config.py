"""Saved pipeline configuration: CRUD, validation, persistence, cleanup."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.conftest import upload_bytes

PIPELINE = {
    "steps": [
        {
            "id": "norm",
            "type": "normalize",
            "config": {
                "columns": [{"column": "cust_nm", "operations": ["trim", "title_case"]}],
                "date_format": "%Y-%m-%d",
                "day_first": False,
            },
        },
        {
            "id": "dedupe",
            "type": "dedupe",
            "enabled": False,
            "config": {"mode": "columns", "columns": ["mail"], "keep": "last"},
        },
        {
            "id": "rename",
            "type": "rename",
            "config": {"rename": {"cust_nm": "customer_name"}, "drop": [], "order": []},
        },
    ]
}


@pytest.fixture()
def job(client: TestClient) -> str:
    return upload_bytes(client, b"cust_nm,mail\nJo,j@x.com\nAl,a@x.com\n", "people.csv")["job_id"]


class TestPipelineCRUD:
    def test_get_without_saved_pipeline_is_404(self, client: TestClient, job: str):
        response = client.get(f"/api/jobs/{job}/pipeline")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "pipeline_not_found"

    def test_save_and_load_roundtrip(self, client: TestClient, job: str):
        saved = client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE)
        assert saved.status_code == 200
        body = saved.json()
        assert body["job_id"] == job
        assert body["version"] == 1
        assert [s["id"] for s in body["steps"]] == ["norm", "dedupe", "rename"]
        assert body["steps"][1]["enabled"] is False
        assert body["created_at"] and body["updated_at"]

        loaded = client.get(f"/api/jobs/{job}/pipeline").json()
        assert loaded["steps"] == body["steps"]

    def test_replace_updates_and_keeps_created_at(self, client: TestClient, job: str):
        first = client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE).json()
        replacement = {"steps": [PIPELINE["steps"][2]]}
        second = client.put(f"/api/jobs/{job}/pipeline", json=replacement).json()
        assert [s["id"] for s in second["steps"]] == ["rename"]
        assert second["created_at"] == first["created_at"]  # preserved on update
        assert second["updated_at"] >= first["updated_at"]

    def test_delete_then_404(self, client: TestClient, job: str):
        client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE)
        deleted = client.delete(f"/api/jobs/{job}/pipeline")
        assert deleted.status_code == 200
        assert deleted.json() == {"job_id": job, "deleted": True}
        assert client.delete(f"/api/jobs/{job}/pipeline").status_code == 404
        assert client.get(f"/api/jobs/{job}/pipeline").status_code == 404

    def test_per_job_isolation(self, client: TestClient, job: str):
        other = upload_bytes(client, b"a,b\n1,2\n", "other.csv")["job_id"]
        client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE)
        assert client.get(f"/api/jobs/{other}/pipeline").status_code == 404
        assert client.get(f"/api/jobs/{job}/pipeline").status_code == 200


class TestPipelineValidation:
    def test_unknown_step_type_rejected(self, client: TestClient, job: str):
        response = client.put(
            f"/api/jobs/{job}/pipeline",
            json={"steps": [{"id": "x", "type": "teleport", "config": {}}]},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_duplicate_step_ids_rejected(self, client: TestClient, job: str):
        step = {"id": "same", "type": "dedupe", "config": {"mode": "exact"}}
        response = client.put(f"/api/jobs/{job}/pipeline", json={"steps": [step, step]})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "duplicate_pipeline_step"

    def test_malformed_body_rejected(self, client: TestClient, job: str):
        assert client.put(f"/api/jobs/{job}/pipeline", json={"steps": []}).status_code == 422
        assert client.put(f"/api/jobs/{job}/pipeline", json={"nope": True}).status_code == 422
        # extra keys inside a step config are forbidden
        bad = {"steps": [{"id": "d", "type": "dedupe", "config": {"mode": "exact", "boom": 1}}]}
        assert client.put(f"/api/jobs/{job}/pipeline", json=bad).status_code == 422

    def test_invalid_rule_config_rejected(self, client: TestClient, job: str):
        bad = {
            "steps": [
                {
                    "id": "v",
                    "type": "validate",
                    "config": {"rules": [{"column": "mail", "rule": "numeric_range"}]},
                }
            ]
        }
        response = client.put(f"/api/jobs/{job}/pipeline", json=bad)
        assert response.status_code == 422

    def test_unknown_job_404(self, client: TestClient):
        response = client.put(
            "/api/jobs/does-not-exist-42/pipeline",
            json={"steps": [{"id": "d", "type": "dedupe", "config": {"mode": "exact"}}]},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "job_not_found"


class TestPipelineLifecycle:
    def test_transform_run_records_used_config(self, client: TestClient, job: str):
        client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE)
        client.post(
            f"/api/jobs/{job}/transform",
            json={"steps": [PIPELINE["steps"][0], PIPELINE["steps"][1]]},
        )
        runs = client.get(f"/api/jobs/{job}/runs?kind=transform").json()
        pipeline_config = runs[0]["summary"]["pipeline"]
        assert pipeline_config["version"] == 1
        assert [s["id"] for s in pipeline_config["steps"]] == ["norm", "dedupe"]

    def test_run_uses_current_editor_config_not_necessarily_saved(
        self, client: TestClient, job: str
    ):
        """A transform run records exactly the steps it was given."""
        client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE)
        different = {
            "steps": [{"id": "only-dedupe", "type": "dedupe", "config": {"mode": "exact"}}]
        }
        client.post(f"/api/jobs/{job}/transform", json=different)
        runs = client.get(f"/api/jobs/{job}/runs?kind=transform").json()
        assert [s["id"] for s in runs[0]["summary"]["pipeline"]["steps"]] == ["only-dedupe"]
        # the saved config is untouched by running something else
        saved = client.get(f"/api/jobs/{job}/pipeline").json()
        assert [s["id"] for s in saved["steps"]] == ["norm", "dedupe", "rename"]

    def test_saved_pipeline_can_be_replayed_directly(self, client: TestClient, job: str):
        """The stored steps are a valid transform request: save → run verbatim."""
        client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE)
        saved = client.get(f"/api/jobs/{job}/pipeline").json()
        replay = client.post(f"/api/jobs/{job}/transform", json={"steps": saved["steps"]})
        assert replay.status_code == 200, replay.json()
        assert replay.json()["output_rows"] == 2

    def test_job_delete_removes_pipeline_and_runs(self, client: TestClient, job: str, data_dir):
        client.put(f"/api/jobs/{job}/pipeline", json=PIPELINE)
        client.post(
            f"/api/jobs/{job}/transform",
            json={"steps": [{"id": "d", "type": "dedupe", "config": {"mode": "exact"}}]},
        )
        assert client.delete(f"/api/jobs/{job}").status_code == 200

        conn = sqlite3.connect(get_settings().db_path)
        try:
            pipelines = conn.execute("SELECT COUNT(*) FROM pipeline_configs").fetchone()[0]
            runs = conn.execute("SELECT COUNT(*) FROM processing_runs").fetchone()[0]
            jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        finally:
            conn.close()
        assert (pipelines, runs, jobs) == (0, 0, 0)

    def test_schema_table_created_on_existing_database(self, client: TestClient, data_dir):
        """Migration path: init_db adds pipeline_configs to an older DB file."""
        from app.db.database import init_db

        init_db()  # idempotent re-run on the same DB file
        conn = sqlite3.connect(get_settings().db_path)
        try:
            tables = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            conn.close()
        assert {"files", "jobs", "processing_runs", "pipeline_configs"} <= tables
