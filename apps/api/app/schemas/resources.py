from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.models.common import DomainEntityType, ThemeMode
from app.schemas.common import ApiModel, CurrencyCode
from app.schemas.domain import HEX_COLOR_PATTERN


class WorkspaceResponse(ApiModel):
    id: UUID
    name: str
    description: str | None
    is_default: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class WorkspaceUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    revision: int = Field(ge=1)


class PreferencesResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    timezone: str
    locale: str
    currency_code: str
    week_starts_on: int
    theme: ThemeMode
    session_timeout_minutes: int
    revision: int
    created_at: datetime
    updated_at: datetime


class PreferencesUpdate(ApiModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    locale: str | None = Field(default=None, min_length=2, max_length=32)
    currency_code: CurrencyCode | None = None
    week_starts_on: int | None = Field(default=None, ge=0, le=6)
    theme: ThemeMode | None = None
    session_timeout_minutes: int | None = Field(default=None, ge=1, le=1_440)
    revision: int = Field(ge=1)


class TagCreate(ApiModel):
    name: str = Field(min_length=1, max_length=80)
    color: str | None = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str | None) -> str | None:
        if value is not None and HEX_COLOR_PATTERN.fullmatch(value) is None:
            raise ValueError("color must use #RRGGBB format")
        return value.upper() if value is not None else None


class TagResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    color: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class TimelineEventResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    entity_type: DomainEntityType
    entity_id: UUID
    action: str
    title: str
    occurred_at: datetime
    payload: dict[str, Any]


class MetaEnumsResponse(ApiModel):
    enums: dict[str, list[str]]
