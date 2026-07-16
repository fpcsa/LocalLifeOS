from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.db.transactions import transaction
from app.models import SystemSetting
from app.schemas.privacy import DeleteAllLocalDataResponse, PrivacyStatusResponse
from app.services.backups import database_path, list_backup_summaries
from app.services.seed import seed_default_data
from app.services.storage_lock import STORAGE_LOCK
from app.services.workspace import get_preferences


def privacy_status(session: Session) -> PrivacyStatusResponse:
    settings = get_settings()
    preferences = get_preferences(session)
    summaries = list_backup_summaries()
    if (
        settings.attachments_dir is None
        or settings.backups_dir is None
        or settings.imports_dir is None
    ):
        raise RuntimeError("local storage directories were not configured")
    return PrivacyStatusResponse(
        data_directory=settings.data_dir,
        database_path=database_path(settings),
        attachments_directory=settings.attachments_dir,
        backups_directory=settings.backups_dir,
        imports_directory=settings.imports_dir,
        network_mode="loopback-only",
        telemetry_enabled=False,
        external_requests_enabled=settings.external_requests_enabled,
        outbound_guard_active=not settings.external_requests_enabled,
        max_attachment_bytes=settings.max_attachment_bytes,
        max_import_bytes=settings.max_import_bytes,
        max_backup_bytes=settings.max_backup_bytes,
        session_timeout_minutes=preferences.session_timeout_minutes,
        privacy_lock_scope="casual-screen-privacy",
        last_backup=summaries[0] if summaries else None,
    )


def _file_count(root: Path) -> int:
    return sum(1 for path in root.rglob("*") if path.is_file()) if root.exists() else 0


def _database_record_count(session: Session) -> int:
    table_names = (
        session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'notes_fts%' "
                "AND name NOT IN ('alembic_version', 'system_settings')"
            )
        )
        .scalars()
        .all()
    )
    total = 0
    for raw_name in table_names:
        name = str(raw_name)
        if not name.replace("_", "").isalnum():
            continue
        total += int(session.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one())
    return total


def _workspace_delete_order(session: Session) -> list[str]:
    table_names = {
        str(name)
        for name in session.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        )
        .scalars()
        .all()
        if str(name).replace("_", "").isalnum()
    }
    scoped = {"workspaces"}
    for table_name in table_names:
        columns = session.execute(text(f'PRAGMA table_info("{table_name}")')).all()
        if any(str(column[1]) == "workspace_id" for column in columns):
            scoped.add(table_name)

    edges: dict[str, set[str]] = {table_name: set() for table_name in scoped}
    incoming = {table_name: 0 for table_name in scoped}
    for child in scoped:
        foreign_keys = session.execute(text(f'PRAGMA foreign_key_list("{child}")')).all()
        for foreign_key in foreign_keys:
            parent = str(foreign_key[2])
            if parent in scoped and parent != child and parent not in edges[child]:
                edges[child].add(parent)
                incoming[parent] += 1

    ready = sorted(table_name for table_name, count in incoming.items() if count == 0)
    ordered: list[str] = []
    while ready:
        child = ready.pop(0)
        ordered.append(child)
        for parent in sorted(edges[child]):
            incoming[parent] -= 1
            if incoming[parent] == 0:
                ready.append(parent)
                ready.sort()
    if len(ordered) != len(scoped) or ordered[-1:] != ["workspaces"]:
        raise RuntimeError("workspace table dependencies could not be ordered safely")
    return ordered


def _delete_workspace_records(session: Session) -> None:
    for table_name in _workspace_delete_order(session):
        session.execute(text(f'DELETE FROM "{table_name}"'))
    session.expire_all()


def _stage_directory(root: Path, identifier: str) -> tuple[Path | None, int]:
    count = _file_count(root)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return None, count
    staged = root.parent / f".{root.name}.delete-{identifier}"
    os.replace(root, staged)
    root.mkdir(parents=True, exist_ok=True)
    return staged, count


def _restore_staged(root: Path, staged: Path | None) -> None:
    if staged is None:
        return
    shutil.rmtree(root, ignore_errors=True)
    os.replace(staged, root)


def delete_all_local_data(
    session: Session,
    *,
    include_backups: bool,
) -> DeleteAllLocalDataResponse:
    settings = get_settings()
    if (
        settings.attachments_dir is None
        or settings.imports_dir is None
        or settings.backups_dir is None
    ):
        raise RuntimeError("local storage directories were not configured")
    identifier = uuid4().hex
    staged: list[tuple[Path, Path | None]] = []
    attachment_count = 0
    import_count = 0
    backup_count = 0
    with STORAGE_LOCK:
        try:
            attachment_stage, attachment_count = _stage_directory(
                settings.attachments_dir, identifier
            )
            staged.append((settings.attachments_dir, attachment_stage))
            import_stage, import_count = _stage_directory(settings.imports_dir, identifier)
            staged.append((settings.imports_dir, import_stage))
            if include_backups:
                backup_stage, backup_count = _stage_directory(settings.backups_dir, identifier)
                staged.append((settings.backups_dir, backup_stage))
            record_count = _database_record_count(session)
            with transaction(session):
                _delete_workspace_records(session)
                timezone_setting = session.exec(
                    select(SystemSetting).where(col(SystemSetting.key) == "user.timezone")
                ).first()
                if timezone_setting is not None:
                    timezone_setting.value = settings.default_timezone
                    session.add(timezone_setting)
                seed_default_data(
                    session,
                    timezone=settings.default_timezone,
                    currency_code=settings.default_currency,
                )
        except Exception:
            for root, staged_path in reversed(staged):
                _restore_staged(root, staged_path)
            raise
        for _, staged_path in staged:
            if staged_path is not None:
                shutil.rmtree(staged_path)
    return DeleteAllLocalDataResponse(
        deleted_database_records=record_count,
        deleted_attachment_files=attachment_count,
        deleted_import_files=import_count,
        deleted_backup_files=backup_count,
        preserved_backups=not include_backups,
    )
