from __future__ import annotations

import ipaddress
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _resolve_path(value: Path, *, base: Path = REPOSITORY_ROOT) -> Path:
    path = value if value.is_absolute() else base / value
    return path.resolve()


def _require_child(path: Path, parent: Path, label: str) -> Path:
    if not path.is_relative_to(parent):
        raise ValueError(f"{label} must be located inside LOCALLIFE_DATA_DIR")
    return path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_prefix="LOCALLIFE_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "LocalLife OS API"
    app_version: str = "0.1.0"
    env: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    container_mode: bool = False
    port: int = Field(default=8000, ge=1, le=65535)
    data_dir: Path = REPOSITORY_ROOT / "data"
    database_url: str | None = None
    attachments_dir: Path | None = None
    backups_dir: Path | None = None
    imports_dir: Path | None = None
    runtime_dir: Path | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ]
    )
    default_timezone: str = "UTC"
    default_currency: str = "EUR"
    max_attachment_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=1024 * 1024 * 1024)
    scheduling_preview_ttl_minutes: int = Field(default=60, ge=1, le=1_440)
    max_import_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=1024 * 1024 * 1024)
    max_import_rows: int = Field(default=10_000, ge=1, le=100_000)
    max_backup_bytes: int = Field(default=2 * 1024 * 1024 * 1024, ge=1024 * 1024)
    backup_argon2_memory_kib: int = Field(default=65_536, ge=8 * 1024, le=1024 * 1024)
    backup_argon2_time_cost: int = Field(default=3, ge=1, le=10)
    backup_argon2_parallelism: int = Field(default=4, ge=1, le=16)
    automation_scheduler_enabled: bool = True
    telemetry_enabled: bool = False
    external_requests_enabled: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return parsed

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        if not origins:
            raise ValueError("at least one local CORS origin is required")

        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"CORS origin must be loopback-only: {origin}")
        return origins

    @field_validator("telemetry_enabled")
    @classmethod
    def require_disabled_telemetry(cls, value: bool) -> bool:
        if value:
            raise ValueError("telemetry must remain disabled")
        return value

    @field_validator("default_currency")
    @classmethod
    def validate_default_currency(cls, value: str) -> str:
        from app.models.common import normalize_currency_code

        return normalize_currency_code(value)

    @field_validator("default_timezone")
    @classmethod
    def validate_default_timezone(cls, value: str) -> str:
        from app.schemas.common import validate_timezone_name

        return validate_timezone_name(value)

    @model_validator(mode="after")
    def resolve_storage(self) -> Settings:
        try:
            loopback_host = ipaddress.ip_address(self.host.strip("[]")).is_loopback
        except ValueError:
            loopback_host = self.host.casefold() == "localhost"
        if not loopback_host and not (self.container_mode and self.host == "0.0.0.0"):
            raise ValueError("LOCALLIFE_HOST must be loopback-only outside a container")

        data_dir = _resolve_path(self.data_dir)
        self.data_dir = data_dir

        path_fields = {
            "attachments_dir": self.attachments_dir or data_dir / "attachments",
            "backups_dir": self.backups_dir or data_dir / "backups",
            "imports_dir": self.imports_dir or data_dir / "imports",
            "runtime_dir": self.runtime_dir or data_dir / "runtime",
        }
        for field_name, value in path_fields.items():
            resolved = _resolve_path(Path(value))
            setattr(self, field_name, _require_child(resolved, data_dir, field_name))

        if self.database_url is None:
            database_path = data_dir / "locallife.db"
            self.database_url = f"sqlite:///{database_path.as_posix()}"
        elif not self.database_url.startswith("sqlite:///"):
            raise ValueError("LocalLife OS only supports local SQLite database URLs")
        else:
            database_location = self.database_url.removeprefix("sqlite:///")
            if database_location != ":memory:":
                database_path = _require_child(
                    _resolve_path(Path(database_location)),
                    data_dir,
                    "database",
                )
                self.database_url = f"sqlite:///{database_path.as_posix()}"

        return self

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.attachments_dir,
            self.backups_dir,
            self.imports_dir,
            self.runtime_dir,
        ):
            if directory is not None:
                directory.mkdir(parents=True, exist_ok=True)

    @property
    def trusted_hosts(self) -> list[str]:
        hosts = ["127.0.0.1", "localhost", "[::1]"]
        if self.env == "test":
            hosts.append("testserver")
        return hosts


@lru_cache
def get_settings() -> Settings:
    return Settings()
