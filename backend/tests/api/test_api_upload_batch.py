"""Batch upload endpoint: per-file isolation, limits, mixed outcomes."""

import io

from fastapi.testclient import TestClient

from tests.conftest import upload_bytes


def batch(client: TestClient, *files: tuple[str, bytes]) -> dict:
    return client.post(
        "/api/files/upload-batch",
        files=[
            ("files", (name, io.BytesIO(content), "application/octet-stream"))
            for name, content in files
        ],
    )


class TestBatchUpload:
    def test_multiple_valid_files_each_get_a_job(self, client: TestClient):
        response = batch(
            client,
            ("one.csv", b"a,b\n1,2\n"),
            ("two.csv", b"c,d\n3,4\n"),
            ("three.csv", b"e,f\n5,6\n"),
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["uploaded"], body["failed"]) == (3, 0)
        job_ids = {item["job_id"] for item in body["results"]}
        assert len(job_ids) == 3
        listed = client.get("/api/jobs").json()
        assert {j["job_id"] for j in listed} >= job_ids

    def test_one_bad_file_does_not_block_the_others(self, client: TestClient):
        response = batch(
            client,
            ("good.csv", b"a,b\n1,2\n"),
            ("virus.exe", b"MZ\xff"),
            ("empty.csv", b""),
            ("another.csv", b"c,d\n3,4\n"),
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["uploaded"], body["failed"]) == (2, 2)
        by_name = {item["filename"]: item for item in body["results"]}
        assert by_name["good.csv"]["status"] == "uploaded"
        assert by_name["another.csv"]["status"] == "uploaded"
        assert by_name["virus.exe"]["status"] == "failed"
        assert by_name["virus.exe"]["error"]["code"] == "unsupported_file_type"
        assert by_name["empty.csv"]["error"]["code"] == "empty_file"
        # failed items carry no job
        assert by_name["virus.exe"]["job_id"] is None
        # successes are fully usable jobs
        detail = client.get(f"/api/jobs/{by_name['good.csv']['job_id']}").json()
        assert detail["row_count"] == 1

    def test_batch_limit_rejected_with_clean_error(self, client: TestClient):
        response = batch(client, *((f"f{i}.csv", b"a\n1\n") for i in range(11)))
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "batch_too_many_files"

    def test_empty_batch_rejected(self, client: TestClient):
        response = client.post("/api/files/upload-batch", files=[])
        assert response.status_code == 422

    def test_batch_result_includes_row_counts(self, client: TestClient):
        body = batch(client, ("data.csv", b"a,b\n1,2\n3,4\n")).json()
        item = body["results"][0]
        assert item["row_count"] == 2
        assert item["column_count"] == 2
        assert item["stored_filename"] == "data.csv"
        assert item["size_bytes"] > 0

    def test_single_file_endpoint_still_works(self, client: TestClient):
        """The original single upload endpoint is unchanged."""
        body = upload_bytes(client, b"a,b\n1,2\n", "solo.csv")
        assert body["row_count"] == 1
        assert client.get(f"/api/jobs/{body['job_id']}").status_code == 200

    def test_batch_success_file_can_be_processed(self, client: TestClient):
        """A file uploaded in a batch flows through the normal pipeline."""
        body = batch(client, ("flow.csv", b"mail\nj@x.com\nj@x.com\n")).json()
        job_id = body["results"][0]["job_id"]
        transform = client.post(
            f"/api/jobs/{job_id}/transform",
            json={"steps": [{"id": "d", "type": "dedupe", "config": {"mode": "exact"}}]},
        )
        assert transform.json()["output_rows"] == 1
