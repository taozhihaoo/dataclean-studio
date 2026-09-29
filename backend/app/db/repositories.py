"""Repository functions for the files / jobs / processing_runs tables."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.core.utils import new_id, utc_now_iso
from app.db.database import db


def _rows(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _row(conn: sqlite3.Connection, query: str, params: tuple = ()) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


# --- files -----------------------------------------------------------------


def create_file(
    original_filename: str, stored_path: str, size_bytes: int, content_kind: str
) -> dict[str, Any]:
    file_id = new_id()
    now = utc_now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO files (id, original_filename, stored_path, size_bytes, content_kind,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (file_id, original_filename, stored_path, size_bytes, content_kind, now),
        )
    return {
        "id": file_id,
        "original_filename": original_filename,
        "stored_path": stored_path,
        "size_bytes": size_bytes,
        "content_kind": content_kind,
        "created_at": now,
    }


def get_file(file_id: str) -> dict[str, Any] | None:
    with db() as conn:
        return _row(conn, "SELECT * FROM files WHERE id = ?", (file_id,))


# --- jobs ------------------------------------------------------------------


def create_job(
    filename: str,
    source: str = "upload",
    file_id: str | None = None,
    row_count: int | None = None,
    column_count: int | None = None,
) -> dict[str, Any]:
    job_id = new_id()
    now = utc_now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO jobs (id, file_id, filename, source, status, row_count, column_count,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, 'ready', ?, ?, ?, ?)",
            (job_id, file_id, filename, source, row_count, column_count, now, now),
        )
    return get_job(job_id)  # type: ignore[return-value]


def get_job(job_id: str) -> dict[str, Any] | None:
    with db() as conn:
        return _row(conn, "SELECT * FROM jobs WHERE id = ?", (job_id,))


def list_jobs() -> list[dict[str, Any]]:
    with db() as conn:
        return _rows(conn, "SELECT * FROM jobs ORDER BY created_at DESC, id DESC")


def update_job(
    job_id: str,
    status: str | None = None,
    row_count: int | None = None,
    column_count: int | None = None,
    filename: str | None = None,
) -> None:
    fields: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("status", status),
        ("row_count", row_count),
        ("column_count", column_count),
        ("filename", filename),
    ):
        if value is not None:
            fields.append(f"{column} = ?")
            params.append(value)
    if not fields:
        return
    fields.append("updated_at = ?")
    params.extend([utc_now_iso(), job_id])
    with db() as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", tuple(params))


def delete_job(job_id: str) -> str | None:
    """Delete a job (runs cascade) and return its file_id, if any."""
    with db() as conn:
        job = _row(conn, "SELECT file_id FROM jobs WHERE id = ?", (job_id,))
        if not job:
            return None
        conn.execute("DELETE FROM processing_runs WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    return job["file_id"]


def delete_file(file_id: str) -> dict[str, Any] | None:
    """Delete a file record (if not referenced by any job) and return it."""
    with db() as conn:
        still_used = _row(conn, "SELECT id FROM jobs WHERE file_id = ?", (file_id,))
        if still_used:
            return None
        record = _row(conn, "SELECT * FROM files WHERE id = ?", (file_id,))
        if record:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    return record


# --- processing runs ---------------------------------------------------------


def create_run(job_id: str, kind: str, status: str, summary: dict | None) -> str:
    run_id = new_id()
    with db() as conn:
        conn.execute(
            "INSERT INTO processing_runs (id, job_id, kind, status, summary, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, job_id, kind, status, _dumps(summary), utc_now_iso()),
        )
    return run_id


def list_runs(job_id: str, kind: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM processing_runs WHERE job_id = ?"
    params: tuple = (job_id,)
    if kind:
        query += " AND kind = ?"
        params = (job_id, kind)
    with db() as conn:
        rows = _rows(conn, query + " ORDER BY created_at DESC, id DESC", params)
    for row in rows:
        row["summary"] = _loads(row.get("summary"))
    return rows


def _loads(raw: str | None) -> dict | None:
    import json

    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _dumps(summary: dict | None) -> str | None:
    import json

    return None if summary is None else json.dumps(summary, ensure_ascii=False)
