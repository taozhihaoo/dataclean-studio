"""End-to-end integration tests: HTTP API -> services -> SQLite -> exports."""

import json

from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes


class TestFullCleaningFlow:
    def test_upload_schema_validate_transform_dedupe_export(self, client: TestClient, data_dir):
        """The complete portfolio demo path against real demo-shaped data."""
        csv_bytes = make_csv(
            "  John Smith  ,JOHN@Example.com,+1 (555) 010-1234,2025-01-15, active",
            "jane doe,jane@example.com,555-010-5678,01/20/2025,ACTIVE",
            "  John Smith  ,JOHN@Example.com,+1 (555) 010-1234,2025-01-15, active",
            "Bad Mail,not-an-email,555.010.2222,2025-04-08,inactive",
            'Al Coda,,5550103333,"Mar 10, 2025",',
            header="cust_nm,mail,ph_no,created_at,status",
        )
        upload = upload_bytes(client, csv_bytes, "people.csv")
        job_id = upload["job_id"]
        assert upload["row_count"] == 5

        # 1. Schema detection
        detail = client.get(f"/api/jobs/{job_id}").json()
        types = {c["name"]: c["detected_type"] for c in detail["columns"]}
        assert types["mail"] == "email"
        assert types["ph_no"] == "phone"
        assert types["created_at"] == "date"

        # 2. Validation
        validation = client.post(
            f"/api/jobs/{job_id}/validate",
            json={
                "rules": [
                    {"column": "mail", "rule": "email"},
                    {
                        "column": "status",
                        "rule": "allowed_values",
                        "values": ["active", "inactive"],
                    },
                ]
            },
        ).json()
        # email: not-an-email; status: " active", "ACTIVE", " active" (case/spacing)
        assert validation["error_count_total"] == 4

        # 3. Transform: normalize -> dedupe by email -> rename
        transform = client.post(
            f"/api/jobs/{job_id}/transform",
            json={
                "steps": [
                    {
                        "id": "norm",
                        "type": "normalize",
                        "config": {
                            "columns": [
                                {"column": "cust_nm", "operations": ["trim", "title_case"]},
                                {"column": "mail", "operations": ["trim", "lowercase"]},
                                {"column": "created_at", "operations": ["normalize_date"]},
                                {"column": "ph_no", "operations": ["normalize_phone"]},
                                {
                                    "column": "status",
                                    "operations": ["trim", "lowercase", "empty_to_null"],
                                },
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
                        "config": {
                            "rename": {
                                "cust_nm": "customer_name",
                                "mail": "email",
                                "ph_no": "phone",
                                "created_at": "registered_on",
                            }
                        },
                    },
                ]
            },
        ).json()
        assert transform["output_rows"] == 4  # dup email removed
        assert transform["columns"] == [
            "customer_name",
            "email",
            "phone",
            "registered_on",
            "status",
        ]
        preview_rows = transform["preview"]
        assert preview_rows[0]["customer_name"] == "John Smith"
        assert preview_rows[0]["phone"] == "+15550101234"
        assert preview_rows[0]["registered_on"] == "2025-01-15"
        assert preview_rows[0]["status"] == "active"

        # 4. Export all three formats
        csv_export = client.post(
            f"/api/jobs/{job_id}/export", json={"file_format": "csv", "filename": "clean"}
        )
        assert csv_export.status_code == 200
        assert csv_export.content.decode("utf-8-sig").splitlines()[0] == (
            "customer_name,email,phone,registered_on,status"
        )

        json_export = client.post(f"/api/jobs/{job_id}/export", json={"file_format": "json"})
        records = json.loads(json_export.content)
        assert len(records) == 4

        xlsx_export = client.post(f"/api/jobs/{job_id}/export", json={"file_format": "xlsx"})
        assert xlsx_export.status_code == 200
        assert len(xlsx_export.content) > 100

        # 5. Quality report
        report = client.get(f"/api/jobs/{job_id}/quality-report").json()
        assert report["original_rows"] == 5
        assert report["total_rows"] == 4
        assert report["rows_delta"] == -1
        assert report["duplicate_rows"] == 0
        assert report["transform"]["summary"]["output_rows"] == 4

        # 6. Runs were recorded in SQLite
        runs = client.get(f"/api/jobs/{job_id}/runs").json()
        kinds = {run["kind"] for run in runs}
        assert kinds == {"validate", "transform", "export"}

        # 7. Workspace files exist on disk
        assert (data_dir / "workspaces" / job_id / "original.pkl").exists()
        assert (data_dir / "workspaces" / job_id / "current.pkl").exists()

    def test_merge_flow_across_uploads(self, client: TestClient):
        first = upload_bytes(
            client,
            make_csv("Jo,j@x.com", "Al,a@x.com", header="cust_nm,mail"),
            "2024.csv",
        )["job_id"]
        second = upload_bytes(
            client,
            make_csv("Bo,b@x.com", "Cy,c@x.com", header="cust_nm,mail"),
            "2025.csv",
        )["job_id"]
        merged = client.post(
            "/api/merge",
            json={"files": [{"job_id": first}, {"job_id": second}], "mode": "union"},
        ).json()
        export = client.post(f"/api/jobs/{merged['job_id']}/export", json={"file_format": "csv"})
        lines = export.content.decode("utf-8-sig").strip().splitlines()
        assert len(lines) == 5
        assert {line.split(",")[0] for line in lines[1:]} == {"Jo", "Al", "Bo", "Cy"}

    def test_merge_then_clean_merged_output(self, client: TestClient):
        first = upload_bytes(
            client,
            make_csv("Jo,j@x.com", "Al,j@x.com", header="cust_nm,mail"),
            "one.csv",
        )["job_id"]
        second = upload_bytes(
            client,
            make_csv("Bo,j@x.com", "Cy,c@x.com", header="cust_nm,mail"),
            "two.csv",
        )["job_id"]
        merged = client.post(
            "/api/merge",
            json={"files": [{"job_id": first}, {"job_id": second}]},
        ).json()
        transform = client.post(
            f"/api/jobs/{merged['job_id']}/transform",
            json={
                "steps": [
                    {
                        "id": "dedupe",
                        "type": "dedupe",
                        "config": {"mode": "columns", "columns": ["mail"], "keep": "first"},
                    }
                ]
            },
        ).json()
        assert transform["input_rows"] == 4
        assert transform["output_rows"] == 2

    def test_deleted_job_workspace_cleaned(self, client: TestClient, data_dir):
        job_id = upload_bytes(client, make_csv("a,x@x.com,1"), "temp.csv")["job_id"]
        export_dir = data_dir / "exports" / job_id
        client.post(f"/api/jobs/{job_id}/export", json={"file_format": "csv"})
        assert export_dir.exists()
        client.delete(f"/api/jobs/{job_id}")
        assert not export_dir.exists()
        assert not (data_dir / "workspaces" / job_id).exists()
