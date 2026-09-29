import json

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes

ROWS = [
    "John,john@example.com,2025-01-15",
    "Jane,jane@example.com,2025-02-20",
    "Bob,bob@example.com,2025-03-25",
    "Nina,nina@example.com,2025-04-30",
    "Omar,omar@example.com,2025-05-05",
    "Pia,pia@example.com,2025-06-10",
    "Quinn,quinn@example.com,2025-07-15",
    "Rosa,rosa@example.com,2025-08-20",
    "Sam,sam@example.com,2025-09-25",
    "Tina,broken-mail,not-a-date",
    "John,john@example.com,2025-01-15",  # exact duplicate of row 1
]


@pytest.fixture()
def job(client: TestClient) -> str:
    return upload_bytes(client, make_csv(*ROWS, header="name,mail,joined"), "quality.csv")["job_id"]


class TestQualityReport:
    def test_report_before_cleaning(self, client: TestClient, job: str):
        report = client.get(f"/api/jobs/{job}/quality-report").json()
        assert report["total_rows"] == 11
        assert report["total_columns"] == 3
        assert report["null_counts"] == {"name": 0, "mail": 0, "joined": 0}
        assert report["duplicate_rows"] == 1
        assert report["invalid_email_count"] == 1
        assert report["invalid_date_count"] == 1
        assert report["original_rows"] == 11
        assert report["rows_delta"] == 0
        assert report["validation"] is None
        assert report["transform"] is None
        assert len(report["columns"]) == 3

    def test_report_reflects_transform(self, client: TestClient, job: str):
        client.post(
            f"/api/jobs/{job}/transform",
            json={
                "steps": [
                    {
                        "id": "d",
                        "type": "dedupe",
                        "config": {"mode": "exact", "keep": "first"},
                    }
                ]
            },
        )
        report = client.get(f"/api/jobs/{job}/quality-report").json()
        assert report["total_rows"] == 10
        assert report["rows_delta"] == -1
        assert report["duplicate_rows"] == 0
        assert report["transform"]["summary"]["output_rows"] == 10

    def test_report_includes_validation_summary(self, client: TestClient, job: str):
        client.post(
            f"/api/jobs/{job}/validate",
            json={"rules": [{"column": "mail", "rule": "email"}]},
        )
        report = client.get(f"/api/jobs/{job}/quality-report").json()
        assert report["validation"]["summary"]["errors_total"] == 1

    def test_report_json_is_exportable(self, client: TestClient, job: str):
        report = client.get(f"/api/jobs/{job}/quality-report")
        parsed = json.loads(report.content)
        assert parsed["job_id"] == job

    def test_report_404(self, client: TestClient):
        assert client.get("/api/jobs/missing-job-09/quality-report").status_code == 404
