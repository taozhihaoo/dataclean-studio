from pathlib import Path

import pytest

from app.db import repositories
from app.db.database import init_db


@pytest.fixture()
def db_env(data_dir: Path):
    init_db()
    return data_dir


class TestRepositories:
    def test_create_and_get_job(self, db_env):
        job = repositories.create_job(filename="a.csv", row_count=5, column_count=3)
        fetched = repositories.get_job(job["id"])
        assert fetched["filename"] == "a.csv"
        assert fetched["status"] == "ready"
        assert fetched["source"] == "upload"

    def test_list_jobs_newest_first(self, db_env):
        repositories.create_job(filename="a.csv")
        repositories.create_job(filename="b.csv")
        names = {j["filename"] for j in repositories.list_jobs()}
        assert names == {"a.csv", "b.csv"}

    def test_update_job(self, db_env):
        job = repositories.create_job(filename="a.csv", row_count=10)
        repositories.update_job(job["id"], status="transformed", row_count=7)
        fetched = repositories.get_job(job["id"])
        assert fetched["status"] == "transformed"
        assert fetched["row_count"] == 7
        assert fetched["updated_at"] >= job["created_at"]

    def test_runs_cascade_on_job_delete(self, db_env):
        job = repositories.create_job(filename="a.csv")
        repositories.create_run(job["id"], "transform", "success", {"x": 1})
        assert repositories.list_runs(job["id"])
        repositories.delete_job(job["id"])
        assert repositories.get_job(job["id"]) is None
        assert repositories.list_runs(job["id"]) == []

    def test_delete_job_returns_file_id(self, db_env):
        file_record = repositories.create_file("a.csv", "unused", 10, "text")
        job = repositories.create_job(filename="a.csv", file_id=file_record["id"])
        assert repositories.delete_job(job["id"]) == file_record["id"]

    def test_delete_file_skipped_while_referenced(self, db_env):
        file_record = repositories.create_file("a.csv", "unused", 10, "text")
        repositories.create_job(filename="a.csv", file_id=file_record["id"])
        assert repositories.delete_file(file_record["id"]) is None
        assert repositories.get_file(file_record["id"])

    def test_runs_kind_filter(self, db_env):
        job = repositories.create_job(filename="a.csv")
        repositories.create_run(job["id"], "validate", "success", None)
        repositories.create_run(job["id"], "transform", "success", None)
        kinds = [r["kind"] for r in repositories.list_runs(job["id"], kind="validate")]
        assert kinds == ["validate"]

    def test_merge_job_source(self, db_env):
        job = repositories.create_job(filename="merged.csv", source="merge")
        assert job["source"] == "merge"

    def test_db_file_created_in_data_dir(self, db_env):
        assert (db_env / "dataclean.db").exists()
