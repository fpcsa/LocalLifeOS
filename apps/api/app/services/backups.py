from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import struct
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from alembic.config import Config
from alembic.script import ScriptDirectory
from argon2.low_level import ARGON2_VERSION, Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import DomainValidationError
from app.schemas.privacy import BackupFileEntry, BackupManifest, BackupSummary
from app.services.storage_lock import STORAGE_LOCK

API_ROOT = Path(__file__).resolve().parents[2]
BACKUP_EXTENSION = ".llbackup"
ENCRYPTED_MAGIC = b"LLOSBAK1"
ENCRYPTED_FORMAT = "locallife-backup-encrypted"
ENCRYPTED_FORMAT_VERSION = 1
MAX_HEADER_BYTES = 16 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ARCHIVE_ENTRIES = 100_000
READ_CHUNK = 1024 * 1024
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


@dataclass(frozen=True)
class BackupInspection:
    path: Path
    manifest: BackupManifest
    encrypted: bool


@dataclass(frozen=True)
class BackupCreation:
    summary: BackupSummary
    manifest: BackupManifest


@dataclass(frozen=True)
class RestoreResult:
    source: Path
    manifest: BackupManifest
    safety_backup: Path


def _backup_error(code: str, message: str, details: dict[str, Any] | None = None) -> NoReturn:
    raise DomainValidationError(code, message, details)


def database_path(settings: Settings | None = None) -> Path:
    configured = settings or get_settings()
    if configured.database_url is None:
        raise RuntimeError("database URL was not initialized")
    location = configured.database_url.removeprefix("sqlite:///")
    if location == ":memory:":
        _backup_error("backup_memory_database", "An in-memory database cannot be backed up.")
    return Path(location).resolve()


def current_schema_revision() -> str:
    configuration = Config(str(API_ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(API_ROOT / "alembic"))
    head = ScriptDirectory.from_config(configuration).get_current_head()
    if head is None:
        raise RuntimeError("Alembic has no current schema head")
    return head


def _sha256_path(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(READ_CHUNK):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _sha256_bytes(value: bytes) -> tuple[int, str]:
    return len(value), hashlib.sha256(value).hexdigest()


def _set_private_permissions(path: Path) -> None:
    # Windows ACL inheritance remains authoritative when chmod cannot narrow it.
    with suppress(OSError):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _snapshot_database(source_path: Path, target_path: Path) -> None:
    if not source_path.is_file():
        _backup_error("database_missing", "The LocalLife OS database does not exist yet.")
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target, pages=256, sleep=0.01)
        result = target.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            _backup_error("database_integrity", "The database snapshot failed its integrity check.")
    finally:
        target.close()
        source.close()
    _set_private_permissions(target_path)


def _snapshot_metadata(snapshot_path: Path) -> tuple[dict[str, str], dict[str, str | int]]:
    connection = sqlite3.connect(snapshot_path)
    connection.row_factory = sqlite3.Row
    try:
        workspace = connection.execute(
            "SELECT id, name FROM workspaces WHERE is_default = 1 AND deleted_at IS NULL LIMIT 1"
        ).fetchone()
        preferences = connection.execute(
            "SELECT timezone, locale, currency_code, week_starts_on, theme, "
            "session_timeout_minutes FROM user_preferences LIMIT 1"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        _backup_error("database_schema", "The database does not match the expected schema.")
        raise AssertionError from exc
    finally:
        connection.close()
    workspace_metadata = (
        {"id": str(workspace["id"]), "name": str(workspace["name"])}
        if workspace is not None
        else {}
    )
    preference_metadata: dict[str, str | int] = (
        {
            "timezone": str(preferences["timezone"]),
            "locale": str(preferences["locale"]),
            "currency_code": str(preferences["currency_code"]),
            "week_starts_on": int(preferences["week_starts_on"]),
            "theme": str(preferences["theme"]),
            "session_timeout_minutes": int(preferences["session_timeout_minutes"]),
        }
        if preferences is not None
        else {}
    )
    return workspace_metadata, preference_metadata


def _schema_from_snapshot(snapshot_path: Path) -> str:
    connection = sqlite3.connect(snapshot_path)
    try:
        row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
    except sqlite3.DatabaseError as exc:
        _backup_error("database_schema", "The database has no readable migration version.")
        raise AssertionError from exc
    finally:
        connection.close()
    if row is None or not isinstance(row[0], str):
        _backup_error("database_schema", "The database has no migration version.")
    return str(row[0])


def _attachment_files(root: Path) -> Iterator[tuple[str, Path]]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            _backup_error("unsafe_attachment", "Attachment symlinks cannot be backed up.")
        if not path.is_file() or path.name.endswith(".upload"):
            continue
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        yield f"attachments/{relative}", path


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _write_bytes(archive: ZipFile, name: str, value: bytes) -> None:
    info = ZipInfo(name)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | stat.S_IRUSR | stat.S_IWUSR) << 16
    archive.writestr(info, value)


def _derive_key(password: str, *, salt: bytes, header: dict[str, Any]) -> bytes:
    if not password:
        _backup_error("backup_password_empty", "An encryption password cannot be empty.")
    secret = bytearray(password.encode("utf-8"))
    try:
        return hash_secret_raw(
            secret=bytes(secret),
            salt=salt,
            time_cost=int(header["time_cost"]),
            memory_cost=int(header["memory_kib"]),
            parallelism=int(header["parallelism"]),
            hash_len=32,
            type=Type.ID,
            version=int(header["version"]),
        )
    finally:
        for index in range(len(secret)):
            secret[index] = 0


def _encrypt_zip(
    zip_path: Path, output_path: Path, password: str, manifest: BackupManifest
) -> None:
    settings = get_settings()
    payload = zip_path.read_bytes()
    if len(payload) > settings.max_backup_bytes:
        _backup_error(
            "backup_too_large",
            f"Backup containers cannot exceed {settings.max_backup_bytes} bytes.",
        )
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = {
        "name": "argon2id",
        "version": ARGON2_VERSION,
        "memory_kib": settings.backup_argon2_memory_kib,
        "time_cost": settings.backup_argon2_time_cost,
        "parallelism": settings.backup_argon2_parallelism,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
    }
    header = {
        "format": ENCRYPTED_FORMAT,
        "format_version": ENCRYPTED_FORMAT_VERSION,
        "cipher": "AES-256-GCM",
        "created_at": manifest.created_at.isoformat(),
        "schema_revision": manifest.schema_revision,
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "kdf": kdf,
    }
    header_bytes = _canonical_json(header)
    prefix = ENCRYPTED_MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes
    key = bytearray(_derive_key(password, salt=salt, header=kdf))
    try:
        ciphertext = AESGCM(bytes(key)).encrypt(nonce, payload, prefix)
    finally:
        for index in range(len(key)):
            key[index] = 0
    with output_path.open("xb") as output:
        output.write(prefix)
        output.write(ciphertext)
        output.flush()
        os.fsync(output.fileno())


def _backup_filename(created_at: datetime, label: str | None) -> str:
    suffix = ""
    if label is not None:
        if LABEL_PATTERN.fullmatch(label) is None:
            _backup_error(
                "backup_label",
                "Backup labels may contain only letters, numbers, underscores, and hyphens.",
            )
        suffix = f"-{label}"
    timestamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    return f"locallife-{timestamp}{suffix}-{uuid4().hex[:8]}{BACKUP_EXTENSION}"


def create_backup(*, password: str | None = None, label: str | None = None) -> BackupCreation:
    settings = get_settings()
    settings.ensure_directories()
    backups_root = settings.backups_dir
    attachments_root = settings.attachments_dir
    if backups_root is None or attachments_root is None:
        raise RuntimeError("backup storage directories were not configured")
    created_at = datetime.now(UTC)
    final_path = (backups_root / _backup_filename(created_at, label)).resolve()
    if not final_path.is_relative_to(backups_root.resolve()):
        _backup_error("unsafe_backup_path", "The backup destination is unsafe.")

    with (
        STORAGE_LOCK,
        tempfile.TemporaryDirectory(prefix=".backup-", dir=backups_root) as temporary_name,
    ):
        temporary = Path(temporary_name)
        snapshot_path = temporary / "locallife.db"
        zip_path = temporary / "payload.zip"
        output_path = backups_root / f".{final_path.name}.{uuid4().hex}.tmp"
        _snapshot_database(database_path(settings), snapshot_path)
        schema_revision = _schema_from_snapshot(snapshot_path)
        workspace_metadata, preference_metadata = _snapshot_metadata(snapshot_path)
        preferences_bytes = _canonical_json(
            {"workspace": workspace_metadata, "preferences": preference_metadata}
        )

        sources: list[tuple[BackupFileEntry, Path | bytes]] = []
        size, digest = _sha256_path(snapshot_path)
        sources.append(
            (
                BackupFileEntry(
                    path="database/locallife.db",
                    kind="database",
                    size_bytes=size,
                    sha256=digest,
                ),
                snapshot_path,
            )
        )
        size, digest = _sha256_bytes(preferences_bytes)
        sources.append(
            (
                BackupFileEntry(
                    path="preferences.json",
                    kind="preferences",
                    size_bytes=size,
                    sha256=digest,
                ),
                preferences_bytes,
            )
        )
        for archive_name, attachment_path in _attachment_files(attachments_root):
            size, digest = _sha256_path(attachment_path)
            sources.append(
                (
                    BackupFileEntry(
                        path=archive_name,
                        kind="attachment",
                        size_bytes=size,
                        sha256=digest,
                    ),
                    attachment_path,
                )
            )
        manifest = BackupManifest(
            app_version=settings.app_version,
            created_at=created_at,
            schema_revision=schema_revision,
            encrypted=password is not None,
            workspace_metadata=workspace_metadata,
            preference_metadata=preference_metadata,
            files=[entry for entry, _ in sources],
        )
        with ZipFile(zip_path, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            _write_bytes(
                archive,
                "manifest.json",
                _canonical_json(manifest.model_dump(mode="json")),
            )
            for entry, source in sources:
                if isinstance(source, bytes):
                    _write_bytes(archive, entry.path, source)
                else:
                    archive.write(source, entry.path)
        try:
            if password is None:
                with output_path.open("xb") as output, zip_path.open("rb") as input_stream:
                    shutil.copyfileobj(input_stream, output, length=READ_CHUNK)
                    output.flush()
                    os.fsync(output.fileno())
            else:
                _encrypt_zip(zip_path, output_path, password, manifest)
            _set_private_permissions(output_path)
            inspection = inspect_backup(output_path, password=password)
            if inspection.manifest != manifest:
                _backup_error("backup_verification", "The created backup did not verify.")
            os.replace(output_path, final_path)
            _set_private_permissions(final_path)
        except Exception:
            output_path.unlink(missing_ok=True)
            raise

    summary = BackupSummary(
        filename=final_path.name,
        path=final_path,
        created_at=created_at,
        schema_revision=schema_revision,
        encrypted=password is not None,
        size_bytes=final_path.stat().st_size,
        integrity_verified=True,
    )
    return BackupCreation(summary=summary, manifest=manifest)


def _validate_member_name(name: str) -> None:
    pure = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or any(":" in part for part in pure.parts)
    ):
        _backup_error("unsafe_backup_member", "The backup contains an unsafe file path.")


def _read_encrypted_payload(path: Path, password: str | None) -> tuple[bytes, dict[str, Any]]:
    settings = get_settings()
    size = path.stat().st_size
    if size > settings.max_backup_bytes:
        _backup_error(
            "backup_too_large",
            f"Backup containers cannot exceed {settings.max_backup_bytes} bytes.",
        )
    with path.open("rb") as source:
        magic = source.read(len(ENCRYPTED_MAGIC))
        if magic != ENCRYPTED_MAGIC:
            _backup_error("backup_format", "The encrypted backup header is invalid.")
        raw_length = source.read(4)
        if len(raw_length) != 4:
            _backup_error("backup_format", "The encrypted backup header is incomplete.")
        header_length = struct.unpack(">I", raw_length)[0]
        if header_length < 2 or header_length > MAX_HEADER_BYTES:
            _backup_error("backup_format", "The encrypted backup header length is invalid.")
        header_bytes = source.read(header_length)
        if len(header_bytes) != header_length:
            _backup_error("backup_format", "The encrypted backup header is incomplete.")
        ciphertext = source.read()
    try:
        header = json.loads(header_bytes)
        kdf = header["kdf"]
        if (
            header["format"] != ENCRYPTED_FORMAT
            or header["format_version"] != ENCRYPTED_FORMAT_VERSION
            or header["cipher"] != "AES-256-GCM"
            or kdf["name"] != "argon2id"
            or int(kdf["version"]) != ARGON2_VERSION
            or not 8_192 <= int(kdf["memory_kib"]) <= 1024 * 1024
            or not 1 <= int(kdf["time_cost"]) <= 10
            or not 1 <= int(kdf["parallelism"]) <= 16
        ):
            raise ValueError
        salt = base64.b64decode(kdf["salt_b64"], validate=True)
        nonce = base64.b64decode(header["nonce_b64"], validate=True)
        if len(salt) != 16 or len(nonce) != 12:
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        _backup_error("backup_format", "The encrypted backup metadata is invalid.")
        raise AssertionError from exc
    if password is None:
        _backup_error("backup_password_required", "This backup requires its password.")
    prefix = magic + raw_length + header_bytes
    key = bytearray(_derive_key(password, salt=salt, header=kdf))
    try:
        try:
            plaintext = AESGCM(bytes(key)).decrypt(nonce, ciphertext, prefix)
        except InvalidTag as exc:
            _backup_error(
                "backup_authentication_failed",
                "The password is wrong or the encrypted backup was modified.",
            )
            raise AssertionError from exc
    finally:
        for index in range(len(key)):
            key[index] = 0
    return plaintext, header


@contextmanager
def _open_archive(path: Path, password: str | None) -> Iterator[tuple[ZipFile, bool]]:
    with path.open("rb") as source:
        prefix = source.read(len(ENCRYPTED_MAGIC))
    encrypted = prefix == ENCRYPTED_MAGIC
    payload: Path | io.BytesIO
    if encrypted:
        plaintext, _ = _read_encrypted_payload(path, password)
        payload = io.BytesIO(plaintext)
    else:
        payload = path
    try:
        with ZipFile(payload, "r") as archive:
            yield archive, encrypted
    except BadZipFile as exc:
        _backup_error("backup_format", "The backup is not a valid LocalLife OS container.")
        raise AssertionError from exc


def _verify_archive(archive: ZipFile, *, encrypted: bool) -> BackupManifest:
    settings = get_settings()
    infos = archive.infolist()
    if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
        _backup_error("backup_entry_limit", "The backup contains an invalid number of files.")
    names: set[str] = set()
    total_size = 0
    for info in infos:
        _validate_member_name(info.filename)
        if info.filename in names or info.is_dir():
            _backup_error("backup_members", "The backup contains duplicate or invalid members.")
        names.add(info.filename)
        mode = info.external_attr >> 16
        if mode and stat.S_ISLNK(mode):
            _backup_error("backup_symlink", "Backup symlinks are not allowed.")
        total_size += info.file_size
        if total_size > settings.max_backup_bytes:
            _backup_error("backup_too_large", "The expanded backup exceeds the local size limit.")
    try:
        manifest_info = archive.getinfo("manifest.json")
    except KeyError as exc:
        _backup_error("backup_manifest", "The backup manifest is missing.")
        raise AssertionError from exc
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        _backup_error("backup_manifest", "The backup manifest is too large.")
    try:
        manifest = BackupManifest.model_validate_json(archive.read(manifest_info))
    except (ValidationError, UnicodeDecodeError) as exc:
        _backup_error("backup_manifest", "The backup manifest is invalid.")
        raise AssertionError from exc
    if manifest.encrypted != encrypted:
        _backup_error("backup_manifest", "The backup encryption metadata is inconsistent.")
    records = {entry.path: entry for entry in manifest.files}
    if len(records) != len(manifest.files):
        _backup_error("backup_manifest", "The backup manifest contains duplicate file records.")
    if manifest.database_path not in records or manifest.preferences_path not in records:
        _backup_error("backup_manifest", "The backup is missing required workspace files.")
    if names != {"manifest.json", *records.keys()}:
        _backup_error("backup_manifest", "The backup members do not match its manifest.")
    for name, record in records.items():
        info = archive.getinfo(name)
        if info.file_size != record.size_bytes:
            _backup_error("backup_integrity", f"Backup size verification failed for {name}.")
        digest = hashlib.sha256()
        read_size = 0
        with archive.open(info, "r") as source:
            while chunk := source.read(READ_CHUNK):
                read_size += len(chunk)
                digest.update(chunk)
        if read_size != record.size_bytes or digest.hexdigest() != record.sha256:
            _backup_error("backup_integrity", f"Backup checksum verification failed for {name}.")
    return manifest


def inspect_backup(path: Path, *, password: str | None = None) -> BackupInspection:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        _backup_error("backup_missing", "The selected backup file does not exist.")
    with _open_archive(resolved, password) as (archive, encrypted):
        manifest = _verify_archive(archive, encrypted=encrypted)
    return BackupInspection(path=resolved, manifest=manifest, encrypted=encrypted)


def _encrypted_summary(path: Path) -> BackupSummary:
    with path.open("rb") as source:
        magic = source.read(len(ENCRYPTED_MAGIC))
        raw_length = source.read(4)
        if magic != ENCRYPTED_MAGIC or len(raw_length) != 4:
            _backup_error("backup_format", "The backup header is invalid.")
        header_length = struct.unpack(">I", raw_length)[0]
        if not 2 <= header_length <= MAX_HEADER_BYTES:
            _backup_error("backup_format", "The backup header length is invalid.")
        header_bytes = source.read(header_length)
    try:
        header = json.loads(header_bytes)
        created_at = datetime.fromisoformat(str(header["created_at"]))
        schema_revision = str(header["schema_revision"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        _backup_error("backup_format", "The backup header metadata is invalid.")
        raise AssertionError from exc
    return BackupSummary(
        filename=path.name,
        path=path,
        created_at=created_at,
        schema_revision=schema_revision,
        encrypted=True,
        size_bytes=path.stat().st_size,
        integrity_verified=False,
    )


def backup_summary(path: Path) -> BackupSummary:
    with path.open("rb") as source:
        encrypted = source.read(len(ENCRYPTED_MAGIC)) == ENCRYPTED_MAGIC
    if encrypted:
        return _encrypted_summary(path)
    inspection = inspect_backup(path)
    return BackupSummary(
        filename=path.name,
        path=path,
        created_at=inspection.manifest.created_at,
        schema_revision=inspection.manifest.schema_revision,
        encrypted=False,
        size_bytes=path.stat().st_size,
        integrity_verified=True,
    )


def list_backup_summaries() -> list[BackupSummary]:
    root = get_settings().backups_dir
    if root is None or not root.exists():
        return []
    summaries: list[BackupSummary] = []
    for path in root.glob(f"*{BACKUP_EXTENSION}"):
        try:
            summaries.append(backup_summary(path.resolve()))
        except DomainValidationError:
            continue
    return sorted(summaries, key=lambda item: item.created_at, reverse=True)


def _extract_archive(
    source: Path,
    target: Path,
    *,
    password: str | None,
) -> BackupManifest:
    with _open_archive(source, password) as (archive, encrypted):
        manifest = _verify_archive(archive, encrypted=encrypted)
        for record in manifest.files:
            if record.kind == "preferences":
                continue
            relative = (
                Path("locallife.db")
                if record.kind == "database"
                else Path(*PurePosixPath(record.path).parts[1:])
            )
            base = target if record.kind == "database" else target / "attachments"
            destination = (base / relative).resolve()
            if not destination.is_relative_to(base.resolve()):
                _backup_error("unsafe_backup_member", "The backup extraction path is unsafe.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(record.path, "r") as input_file, destination.open("xb") as output:
                shutil.copyfileobj(input_file, output, length=READ_CHUNK)
                output.flush()
                os.fsync(output.fileno())
            _set_private_permissions(destination)
    return manifest


def _quick_check(path: Path) -> None:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=rw", uri=True)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            _backup_error("restore_database_integrity", "The restored database is not valid.")
    finally:
        connection.close()


def _activate_restore(
    staged_database: Path,
    staged_attachments: Path,
    *,
    fault_hook: Callable[[str], None] | None = None,
) -> None:
    settings = get_settings()
    target_database = database_path(settings)
    target_attachments = settings.attachments_dir
    if target_attachments is None:
        raise RuntimeError("attachments directory was not configured")
    identifier = uuid4().hex
    rollback_database = settings.data_dir / f".restore-current-{identifier}.db"
    rollback_attachments = settings.data_dir / f".restore-current-{identifier}-attachments"
    staged_database_copy = settings.data_dir / f".restore-new-{identifier}.db"
    shutil.copy2(staged_database, staged_database_copy)
    _set_private_permissions(staged_database_copy)
    had_database = target_database.exists()
    had_attachments = target_attachments.exists()
    database_swapped = False
    attachments_swapped = False
    if had_database:
        shutil.copy2(target_database, rollback_database)
        _set_private_permissions(rollback_database)
    try:
        for suffix in ("-wal", "-shm"):
            Path(f"{target_database}{suffix}").unlink(missing_ok=True)
        if had_attachments:
            os.replace(target_attachments, rollback_attachments)
        os.replace(staged_attachments, target_attachments)
        attachments_swapped = True
        if fault_hook is not None:
            fault_hook("attachments")
        os.replace(staged_database_copy, target_database)
        database_swapped = True
        if fault_hook is not None:
            fault_hook("database")
        _quick_check(target_database)
        if fault_hook is not None:
            fault_hook("verified")
    except Exception as exc:
        rollback_failures: list[str] = []
        try:
            if database_swapped:
                if had_database and rollback_database.exists():
                    os.replace(rollback_database, target_database)
                elif not had_database:
                    target_database.unlink(missing_ok=True)
        except OSError:
            rollback_failures.append(str(rollback_database))
        try:
            if attachments_swapped:
                shutil.rmtree(target_attachments, ignore_errors=False)
                if had_attachments and rollback_attachments.exists():
                    os.replace(rollback_attachments, target_attachments)
        except OSError:
            rollback_failures.append(str(rollback_attachments))
        if rollback_failures:
            _backup_error(
                "restore_recovery_required",
                "Restore failed and automatic rollback was incomplete. Follow the recovery guide.",
                {"preserved_paths": rollback_failures},
            )
        _backup_error(
            "restore_rolled_back",
            "Restore failed before completion; the original workspace was restored.",
            {"failure_type": type(exc).__name__},
        )
    finally:
        staged_database_copy.unlink(missing_ok=True)
    rollback_database.unlink(missing_ok=True)
    if rollback_attachments.exists():
        shutil.rmtree(rollback_attachments)


def restore_backup(
    path: Path,
    *,
    password: str | None = None,
    fault_hook: Callable[[str], None] | None = None,
) -> RestoreResult:
    source = path.expanduser().resolve()
    inspection = inspect_backup(source, password=password)
    expected_schema = current_schema_revision()
    if inspection.manifest.schema_revision != expected_schema:
        _backup_error(
            "backup_schema_incompatible",
            "The backup schema is not compatible with this LocalLife OS version.",
            {
                "backup_schema": inspection.manifest.schema_revision,
                "application_schema": expected_schema,
            },
        )
    settings = get_settings()
    runtime_root = settings.runtime_dir
    if runtime_root is None:
        raise RuntimeError("runtime directory was not configured")
    runtime_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=runtime_root) as temporary_name:
        temporary = Path(temporary_name)
        extracted_manifest = _extract_archive(source, temporary, password=password)
        staged_database = temporary / "locallife.db"
        staged_attachments = temporary / "attachments"
        staged_attachments.mkdir(exist_ok=True)
        _quick_check(staged_database)
        if _schema_from_snapshot(staged_database) != expected_schema:
            _backup_error(
                "backup_schema_incompatible",
                "The extracted database schema does not match its manifest.",
            )
        with STORAGE_LOCK:
            safety = create_backup(password=password, label="pre-restore")
            _activate_restore(
                staged_database,
                staged_attachments,
                fault_hook=fault_hook,
            )
    return RestoreResult(
        source=source,
        manifest=extracted_manifest,
        safety_backup=safety.summary.path,
    )
