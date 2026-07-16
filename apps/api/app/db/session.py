from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.config import get_settings
from app.db.transactions import transaction
from app.services.seed import seed_default_data

API_ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("database URL was not initialized")
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    if settings.database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def run_migrations() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("database URL was not initialized")
    settings.ensure_directories()

    configuration = Config(str(API_ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(API_ROOT / "alembic"))
    configuration.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(configuration, "head")


def seed_database() -> None:
    settings = get_settings()
    with Session(get_engine()) as session, transaction(session):
        seed_default_data(
            session,
            timezone=settings.default_timezone,
            currency_code=settings.default_currency,
        )


def initialize_database() -> None:
    get_settings().ensure_directories()
    run_migrations()
    seed_database()
