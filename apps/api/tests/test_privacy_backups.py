from __future__ import annotations

import logging
import socket
import sqlite3
from pathlib import Path

import pytest
from app.core.config import Settings, get_settings
from app.core.exceptions import DomainValidationError
from app.core.logging import configure_safe_logging
from app.core.network import configure_outbound_network_guard
from app.db.session import get_engine, initialize_database
from app.services.backups import create_backup, inspect_backup, restore_backup
from fastapi.testclient import TestClient


def _workspace_name(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT name FROM workspaces WHERE is_default = 1 AND deleted_at IS NULL"
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return str(row[0])


def _set_workspace_name(path: Path, name: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE workspaces SET name = ?, revision = revision + 1 WHERE is_default = 1",
            (name,),
        )
        connection.commit()
    finally:
        connection.close()


def test_backup_restore_round_trip_database_attachments_and_preferences(
    database_path: Path,
) -> None:
    initialize_database()
    settings = get_settings()
    assert settings.attachments_dir is not None
    attachment = settings.attachments_dir / "workspace" / "proof.txt"
    attachment.parent.mkdir(parents=True, exist_ok=True)
    attachment.write_text("snapshot attachment", encoding="utf-8")
    _set_workspace_name(database_path, "Snapshot workspace")

    created = create_backup(label="round-trip")
    assert created.summary.integrity_verified is True
    assert {entry.kind for entry in created.manifest.files} == {
        "attachment",
        "database",
        "preferences",
    }

    _set_workspace_name(database_path, "Changed workspace")
    attachment.write_text("changed attachment", encoding="utf-8")
    get_engine().dispose()
    result = restore_backup(created.summary.path)

    assert result.safety_backup.is_file()
    assert _workspace_name(database_path) == "Snapshot workspace"
    assert attachment.read_text(encoding="utf-8") == "snapshot attachment"


def test_encrypted_backup_rejects_wrong_password_and_tampering(database_path: Path) -> None:
    initialize_database()
    created = create_backup(password="correct horse battery staple", label="encrypted")
    inspection = inspect_backup(created.summary.path, password="correct horse battery staple")
    assert inspection.manifest.encrypted is True

    with pytest.raises(DomainValidationError) as wrong_password:
        inspect_backup(created.summary.path, password="wrong password")
    assert wrong_password.value.code == "backup_authentication_failed"

    tampered = created.summary.path.with_name("tampered.llbackup")
    payload = bytearray(created.summary.path.read_bytes())
    payload[-1] ^= 1
    tampered.write_bytes(payload)
    with pytest.raises(DomainValidationError) as modified:
        inspect_backup(tampered, password="correct horse battery staple")
    assert modified.value.code == "backup_authentication_failed"


def test_restore_failure_rolls_back_database_and_attachments(database_path: Path) -> None:
    initialize_database()
    settings = get_settings()
    assert settings.attachments_dir is not None
    attachment = settings.attachments_dir / "rollback.txt"
    attachment.write_text("backup version", encoding="utf-8")
    _set_workspace_name(database_path, "Backup version")
    created = create_backup(label="rollback-source")

    attachment.write_text("current version", encoding="utf-8")
    _set_workspace_name(database_path, "Current version")
    get_engine().dispose()

    def fail_after_database(stage: str) -> None:
        if stage == "database":
            raise RuntimeError("injected restore failure")

    with pytest.raises(DomainValidationError) as failed:
        restore_backup(created.summary.path, fault_hook=fail_after_database)
    assert failed.value.code == "restore_rolled_back"
    assert _workspace_name(database_path) == "Current version"
    assert attachment.read_text(encoding="utf-8") == "current version"


def test_privacy_api_creates_verified_backup_and_reports_local_status(
    client: TestClient,
    database_path: Path,
) -> None:
    status_response = client.get("/api/v1/privacy/status")
    assert status_response.status_code == 200
    status = status_response.json()["data"]
    assert status["network_mode"] == "loopback-only"
    assert status["telemetry_enabled"] is False
    assert status["outbound_guard_active"] is True
    assert status["database_path"] == str(database_path)
    assert status["last_backup"] is None

    backup_response = client.post("/api/v1/privacy/backups", json={"label": "api"})
    assert backup_response.status_code == 201
    backup = backup_response.json()["data"]["backup"]
    assert backup["integrity_verified"] is True
    assert Path(backup["path"]).is_file()


def test_delete_all_requires_exact_phrase_and_preserves_backups_by_default(
    client: TestClient,
) -> None:
    settings = get_settings()
    assert settings.attachments_dir is not None
    assert settings.imports_dir is not None
    attachment = settings.attachments_dir / "delete-me.txt"
    imported = settings.imports_dir / "delete-me.csv"
    attachment.write_text("private", encoding="utf-8")
    imported.write_text("private", encoding="utf-8")
    backup = create_backup(label="preserve").summary.path

    rejected = client.post(
        "/api/v1/privacy/delete-all",
        json={"confirmation": "delete", "include_backups": False},
    )
    assert rejected.status_code == 422
    response = client.post(
        "/api/v1/privacy/delete-all",
        json={"confirmation": "DELETE ALL LOCAL DATA", "include_backups": False},
    )
    assert response.status_code == 200
    assert not attachment.exists()
    assert not imported.exists()
    assert backup.exists()


def test_host_origin_security_headers_and_outbound_guard(client: TestClient) -> None:
    hostile_host = client.get("/api/v1/health", headers={"Host": "attacker.example"})
    assert hostile_host.status_code == 400
    hostile_origin = client.get("/api/v1/health", headers={"Origin": "https://attacker.example"})
    assert hostile_origin.status_code == 403

    response = client.get("/api/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]

    configure_outbound_network_guard(external_requests_enabled=False)
    assert socket.getaddrinfo("localhost", 8000)
    with pytest.raises(PermissionError, match="Outbound network access is disabled"):
        socket.getaddrinfo("example.invalid", 443)


def test_native_settings_reject_public_bind() -> None:
    with pytest.raises(ValueError, match="loopback-only"):
        Settings(host="0.0.0.0", container_mode=False)
    assert Settings(host="0.0.0.0", container_mode=True).host == "0.0.0.0"


def test_sensitive_values_are_redacted_from_logs(caplog: pytest.LogCaptureFixture) -> None:
    configure_safe_logging()
    logger = logging.getLogger("app.privacy-test")
    with caplog.at_level(logging.WARNING):
        logger.warning(
            "note_content=%s transaction_description=%s password=%s",
            "private-note-body",
            "private-transaction",
            "private-password",
        )
    assert "private-note-body" not in caplog.text
    assert "private-transaction" not in caplog.text
    assert "private-password" not in caplog.text
    assert caplog.text.count("[REDACTED]") >= 3
