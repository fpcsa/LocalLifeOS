from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr

from app.schemas.common import ApiModel


class BackupFileEntry(ApiModel):
    path: str = Field(min_length=1, max_length=1000)
    kind: Literal["attachment", "database", "preferences"]
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class BackupManifest(ApiModel):
    format: Literal["locallife-backup"] = "locallife-backup"
    format_version: Literal[1] = 1
    app_version: str
    created_at: datetime
    schema_revision: str
    encrypted: bool
    database_path: Literal["database/locallife.db"] = "database/locallife.db"
    preferences_path: Literal["preferences.json"] = "preferences.json"
    workspace_metadata: dict[str, str]
    preference_metadata: dict[str, str | int]
    files: list[BackupFileEntry]


class BackupSummary(ApiModel):
    filename: str
    path: Path
    created_at: datetime
    schema_revision: str
    encrypted: bool
    size_bytes: int = Field(ge=0)
    integrity_verified: bool


class BackupCreateRequest(ApiModel):
    password: SecretStr | None = None
    label: str | None = Field(default=None, min_length=1, max_length=40)


class BackupCreateResponse(ApiModel):
    backup: BackupSummary
    manifest: BackupManifest


class PrivacyStatusResponse(ApiModel):
    data_directory: Path
    database_path: Path
    attachments_directory: Path
    backups_directory: Path
    imports_directory: Path
    network_mode: Literal["loopback-only"]
    telemetry_enabled: Literal[False]
    external_requests_enabled: bool
    outbound_guard_active: bool
    max_attachment_bytes: int
    max_import_bytes: int
    max_backup_bytes: int
    session_timeout_minutes: int
    privacy_lock_scope: Literal["casual-screen-privacy"]
    last_backup: BackupSummary | None


class DeleteAllLocalDataRequest(ApiModel):
    confirmation: Literal["DELETE ALL LOCAL DATA"]
    include_backups: bool = False


class DeleteAllLocalDataResponse(ApiModel):
    deleted_database_records: int
    deleted_attachment_files: int
    deleted_import_files: int
    deleted_backup_files: int
    preserved_backups: bool
