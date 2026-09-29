"""Shared fixtures: isolated app instances with temp data directories."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "data"
    monkeypatch.setenv("DATA_CLEAN_DATA_DIR", str(path))
    get_settings.cache_clear()
    get_settings().ensure_dirs()
    return path


@pytest.fixture()
def client(data_dir: Path) -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


def make_csv(*rows: str, header: str = "name,mail,age") -> bytes:
    body = "\n".join([header, *rows]) + "\n"
    return body.encode("utf-8")


def upload_bytes(client: TestClient, content: bytes, filename: str) -> dict:
    response = client.post(
        "/api/files/upload",
        files={"upload": (filename, io.BytesIO(content), "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload_customers(client: TestClient) -> str:
    content = make_csv(
        "John Smith,john@example.com,34",
        "Jane Doe,jane@example.com,28",
        "John Smith,john@example.com,34",  # exact duplicate
        "Bob Brown,bob@example.com,44",
        "Jane Doe,jane@example.com,28",  # exact duplicate
        "Nina Patel,not-an-email,26",
        "  Padded Name  ,pad@example.com,55",
    )
    return upload_bytes(client, content, "customers.csv")["job_id"]
