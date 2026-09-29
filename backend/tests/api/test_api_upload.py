import io

import openpyxl
from fastapi.testclient import TestClient

from tests.conftest import make_csv, upload_bytes


class TestUploadEndpoint:
    def test_upload_csv(self, client: TestClient):
        response = client.post(
            "/api/files/upload",
            files={
                "upload": (
                    "data.csv",
                    io.BytesIO(make_csv("a,x@x.com,3", "b,y@y.com,4")),
                    "text/csv",
                )
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["filename"] == "data.csv"
        assert body["row_count"] == 2
        assert body["column_count"] == 3
        assert body["status"] == "ready"

    def test_upload_xlsx(self, client: TestClient):
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.append(["name", "mail"])
        sheet.append(["Jo", "j@x.com"])
        buffer = io.BytesIO()
        book.save(buffer)
        buffer.seek(0)
        response = client.post(
            "/api/files/upload",
            files={"upload": ("data.xlsx", buffer, "application/octet-stream")},
        )
        assert response.status_code == 201
        assert response.json()["row_count"] == 1

    def test_upload_error_shape_is_uniform(self, client: TestClient):
        response = client.post(
            "/api/files/upload",
            files={"upload": ("virus.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        )
        assert response.status_code == 400
        error = response.json()["error"]
        assert set(error) == {"code", "message", "details"}

    def test_unsupported_extension(self, client: TestClient):
        response = client.post(
            "/api/files/upload",
            files={"upload": ("evil.exe", io.BytesIO(b"MZanything"), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unsupported_file_type"

    def test_no_extension(self, client: TestClient):
        response = client.post(
            "/api/files/upload",
            files={"upload": ("noext", io.BytesIO(b"a,b\n1,2"), "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unsupported_file_type"

    def test_content_extension_mismatch(self, client: TestClient):
        """A ZIP renamed to .csv is rejected: sniffing beats the extension."""
        response = client.post(
            "/api/files/upload",
            files={"upload": ("fake.csv", io.BytesIO(b"PK\x03\x04zipdata"), "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "content_type_mismatch"

    def test_binary_junk_rejected(self, client: TestClient):
        response = client.post(
            "/api/files/upload",
            files={"upload": ("junk.csv", io.BytesIO(b"\x00\x01\x02\x03" * 10), "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_encoding"

    def test_empty_upload_rejected(self, client: TestClient):
        response = client.post(
            "/api/files/upload",
            files={"upload": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "empty_file"

    def test_oversized_upload_rejected(self, client: TestClient, data_dir, monkeypatch):
        monkeypatch.setenv("DATA_CLEAN_MAX_UPLOAD_MB", "1")
        from app.config import get_settings

        get_settings.cache_clear()
        payload = b"a,b\n" + b"1,2\n" * 600_000  # ~2.4 MB
        response = client.post(
            "/api/files/upload",
            files={"upload": ("big.csv", io.BytesIO(payload), "text/csv")},
        )
        get_settings.cache_clear()
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "file_too_large"

    def test_directory_traversal_filename_neutralized(self, client: TestClient):
        body = upload_bytes(client, make_csv("a,x@x.com,1"), "../../etc/passwd.csv")
        assert body["filename"] == "passwd.csv"

    def test_uppercase_extension_accepted(self, client: TestClient):
        body = upload_bytes(client, make_csv("a,x@x.com,1"), "DATA.CSV")
        assert body["row_count"] == 1

    def test_client_mime_type_ignored(self, client: TestClient):
        """Server sniffs content; a lying MIME type changes nothing."""
        response = client.post(
            "/api/files/upload",
            files={"upload": ("ok.csv", io.BytesIO(make_csv("a,x@x.com,1")), "application/pdf")},
        )
        assert response.status_code == 201

    def test_stored_file_uses_generated_name(self, client: TestClient, data_dir):
        upload_bytes(client, make_csv("a,x@x.com,1"), "people.csv")
        stored = list((data_dir / "uploads").glob("*__people.csv"))
        assert len(stored) == 1
        assert stored[0].name.startswith(
            ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f")
        )
