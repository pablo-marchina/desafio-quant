import json

import pytest

from app.services.database_backup import (
    _assert_isolated_target,
    _connection_parts,
    verify_manifest,
)


def test_connection_parts_supports_special_password_characters():
    parts = _connection_parts("postgresql://user:p%40ss%23word@db.example.com:5432/postgres")

    assert parts["username"] == "user"
    assert parts["password"] == "p@ss#word"
    assert parts["host"] == "db.example.com"


def test_restore_refuses_source_database_as_target():
    url = "postgresql://user:password@db.example.com:5432/postgres"

    with pytest.raises(ValueError, match="coincide"):
        _assert_isolated_target(url, url)


def test_manifest_verification_detects_tampering(tmp_path):
    backup = tmp_path / "backup.dump"
    backup.write_bytes(b"original")
    import hashlib

    manifest = tmp_path / "backup.manifest.json"
    manifest.write_text(
        json.dumps({"sha256": hashlib.sha256(b"original").hexdigest()}),
        encoding="utf-8",
    )
    assert verify_manifest(backup, manifest) is True

    backup.write_bytes(b"tampered")
    assert verify_manifest(backup, manifest) is False
