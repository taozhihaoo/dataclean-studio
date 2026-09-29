from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes


class TestJobEndpoints:
    def test_job_detail_with_schema(self, client: TestClient):
        job_id = upload_bytes(
            client,
            make_csv(
                "John Smith,john@example.com,34,2025-01-15",
                "Jane Doe,jane@example.com,28,01/20/2025",
                "Nina Cole,nina@example.com,44,2025-03-01",
                "Bad Mail,broken,44,",
                header="cust_nm,mail,age,created_at",
            ),
            "people.csv",
        )["job_id"]
        detail = client.get(f"/api/jobs/{job_id}").json()
        assert detail["filename"] == "people.csv"
        assert detail["row_count"] == 4
        assert detail["column_count"] == 4
        assert detail["is_transformed"] is False
        types = {c["name"]: c["detected_type"] for c in detail["columns"]}
        assert types["mail"] == "email"
        assert types["age"] == "integer"
        assert types["created_at"] == "date"
        mail_profile = next(c for c in detail["columns"] if c["name"] == "mail")
        assert mail_profile["invalid_count"] == 1
        assert mail_profile["null_count"] == 0

    def test_job_not_found_uniform_error(self, client: TestClient):
        response = client.get("/api/jobs/does-not-exist-123")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "job_not_found"

    def test_job_list(self, client: TestClient):
        upload_bytes(client, make_csv("a,x@x.com,1"), "one.csv")
        upload_bytes(client, make_csv("b,y@y.com,2"), "two.csv")
        jobs = client.get("/api/jobs").json()
        assert sorted(j["filename"] for j in jobs) == ["one.csv", "two.csv"]

    def test_preview_limit(self, client: TestClient):
        rows = [f"row{i},m{i}@x.com,{i}" for i in range(60)]
        job_id = upload_bytes(client, make_csv(*rows), "big.csv")["job_id"]
        preview = client.get(f"/api/jobs/{job_id}/preview").json()
        assert len(preview["rows"]) == 50  # default preview limit
        assert preview["total_rows"] == 60
        assert preview["limited"] is True
        small = client.get(f"/api/jobs/{job_id}/preview?limit=5").json()
        assert len(small["rows"]) == 5

    def test_preview_rejects_big_limit(self, client: TestClient):
        job_id = upload_bytes(client, make_csv("a,x@x.com,1"), "a.csv")["job_id"]
        assert client.get(f"/api/jobs/{job_id}/preview?limit=500").status_code == 422

    def test_delete_job_removes_everything(self, client: TestClient, data_dir):
        job_id = upload_bytes(client, make_csv("a,x@x.com,1"), "gone.csv")["job_id"]
        assert client.delete(f"/api/jobs/{job_id}").status_code == 200
        assert client.get(f"/api/jobs/{job_id}").status_code == 404
        assert not (data_dir / "workspaces" / job_id).exists()
        remaining = client.get("/api/jobs").json()
        assert job_id not in [j["job_id"] for j in remaining]

    def test_runs_listing(self, client: TestClient):
        job_id = upload_bytes(client, make_csv("a,x@x.com,1"), "a.csv")["job_id"]
        client.post(
            f"/api/jobs/{job_id}/validate",
            json={"rules": [{"column": "mail", "rule": "email"}]},
        )
        runs = client.get(f"/api/jobs/{job_id}/runs").json()
        assert runs[0]["kind"] == "validate"
        assert runs[0]["summary"]["errors_total"] == 0

    def test_job_id_format_validated(self, client: TestClient):
        assert client.get("/api/jobs/short").status_code == 422
