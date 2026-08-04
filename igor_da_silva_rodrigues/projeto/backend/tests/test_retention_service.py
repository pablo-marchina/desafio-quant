import os
from datetime import UTC, datetime, timedelta

from app.services.retention_service import RetentionPolicy, RetentionService


def _aged_file(path, age_days):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("data", encoding="utf-8")
    timestamp = (datetime.now(UTC) - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_retention_dry_run_does_not_delete_files(tmp_path):
    old_raw = tmp_path / "data/raw/source/old.json"
    recent_raw = tmp_path / "data/raw/source/recent.json"
    _aged_file(old_raw, 181)
    _aged_file(recent_raw, 10)
    service = RetentionService(backend_dir=tmp_path, policy=RetentionPolicy())

    report = service.run(execute=False)

    assert report["mode"] == "dry-run"
    assert report["total_actions"] == 1
    assert old_raw.exists()
    assert recent_raw.exists()


def test_retention_execute_removes_only_expired_managed_files(tmp_path):
    old_raw = tmp_path / "data/raw/source/old.json"
    recent_raw = tmp_path / "data/raw/source/recent.json"
    old_cache = tmp_path / "data/cache/pipeline/old.json"
    _aged_file(old_raw, 181)
    _aged_file(recent_raw, 10)
    _aged_file(old_cache, 31)
    service = RetentionService(backend_dir=tmp_path)

    report = service.run(execute=True)

    assert report["total_actions"] == 2
    assert not old_raw.exists()
    assert not old_cache.exists()
    assert recent_raw.exists()
