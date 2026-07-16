from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.db.session import get_engine, initialize_database
from app.main import create_app
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture
def database_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    data_dir = tmp_path / "data"
    database_path = data_dir / "test.db"
    monkeypatch.setenv("LOCALLIFE_ENV", "test")
    monkeypatch.setenv("LOCALLIFE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("LOCALLIFE_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("LOCALLIFE_EXTERNAL_REQUESTS_ENABLED", "false")
    monkeypatch.setenv("LOCALLIFE_AUTOMATION_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("LOCALLIFE_BACKUP_ARGON2_MEMORY_KIB", "8192")
    monkeypatch.setenv("LOCALLIFE_BACKUP_ARGON2_TIME_COST", "1")
    monkeypatch.setenv("LOCALLIFE_BACKUP_ARGON2_PARALLELISM", "1")
    monkeypatch.setenv(
        "LOCALLIFE_DATABASE_URL",
        f"sqlite:///{database_path.as_posix()}",
    )
    monkeypatch.delenv("LOCALLIFE_ATTACHMENTS_DIR", raising=False)
    monkeypatch.delenv("LOCALLIFE_BACKUPS_DIR", raising=False)
    monkeypatch.delenv("LOCALLIFE_IMPORTS_DIR", raising=False)
    get_settings.cache_clear()
    get_engine.cache_clear()

    yield database_path

    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def client(database_path: Path) -> Iterator[TestClient]:
    del database_path

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def db_session(database_path: Path) -> Iterator[Session]:
    del database_path
    initialize_database()
    with Session(get_engine()) as session:
        yield session
