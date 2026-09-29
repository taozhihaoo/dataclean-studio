import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes


@pytest.fixture()
def batch_one(client: TestClient) -> str:
    return upload_bytes(
        client,
        make_csv("Jo,j@x.com,34", "Al,a@x.com,29", header="cust_nm,mail,age"),
        "batch_one.csv",
    )["job_id"]


@pytest.fixture()
def batch_two(client: TestClient) -> str:
    return upload_bytes(
        client,
        make_csv("Bo,b@x.com,41,north", "Cy,c@x.com,,south", header="cust_nm,mail,age,region"),
        "batch_two.csv",
    )["job_id"]


class TestMergeEndpoint:
    def test_union_merge(self, client: TestClient, batch_one: str, batch_two: str):
        response = client.post(
            "/api/merge",
            json={"files": [{"job_id": batch_one}, {"job_id": batch_two}], "mode": "union"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["output_rows"] == 4
        assert body["columns"] == ["cust_nm", "mail", "age", "region"]
        assert body["null_cells_filled"] == 2  # batch_one has no region column

        merged = client.get(f"/api/jobs/{body['job_id']}").json()
        assert merged["source"] == "merge"
        preview = client.get(f"/api/jobs/{body['job_id']}/preview").json()
        assert preview["rows"][0]["region"] is None
        assert preview["rows"][2]["region"] == "north"

    def test_intersection_merge(self, client: TestClient, batch_one: str, batch_two: str):
        body = client.post(
            "/api/merge",
            json={
                "files": [{"job_id": batch_one}, {"job_id": batch_two}],
                "mode": "intersection",
            },
        ).json()
        assert body["columns"] == ["cust_nm", "mail", "age"]
        assert body["output_rows"] == 4

    def test_merge_with_mapping(self, client: TestClient, batch_one: str, batch_two: str):
        alt = upload_bytes(
            client,
            make_csv("Dee,d@x.com", header="name,mail_address"),
            "alt.csv",
        )["job_id"]
        body = client.post(
            "/api/merge",
            json={
                "files": [
                    {"job_id": batch_one, "mapping": {"mail": "email"}},
                    {
                        "job_id": alt,
                        "mapping": {"name": "cust_nm", "mail_address": "email"},
                    },
                ],
                "mode": "union",
            },
        ).json()
        assert body["columns"] == ["cust_nm", "email", "age"]
        preview = client.get(f"/api/jobs/{body['job_id']}/preview").json()
        assert preview["rows"][0]["email"] == "j@x.com"
        assert preview["rows"][2]["email"] == "d@x.com"

    def test_merge_requires_two_files(self, client: TestClient, batch_one: str):
        response = client.post("/api/merge", json={"files": [{"job_id": batch_one}]})
        assert response.status_code == 422

    def test_merge_duplicate_inputs_rejected(self, client: TestClient, batch_one: str):
        response = client.post(
            "/api/merge",
            json={"files": [{"job_id": batch_one}, {"job_id": batch_one}]},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "duplicate_merge_input"

    def test_merge_unknown_job(self, client: TestClient, batch_one: str):
        response = client.post(
            "/api/merge",
            json={"files": [{"job_id": batch_one}, {"job_id": "missing-job-007"}]},
        )
        assert response.status_code == 404

    def test_merged_job_is_exportable(self, client: TestClient, batch_one: str, batch_two: str):
        merged = client.post(
            "/api/merge",
            json={"files": [{"job_id": batch_one}, {"job_id": batch_two}]},
        ).json()
        response = client.post(f"/api/jobs/{merged['job_id']}/export", json={"file_format": "csv"})
        assert response.status_code == 200
        lines = response.content.decode("utf-8-sig").strip().splitlines()
        assert len(lines) == 5  # header + 4 rows
