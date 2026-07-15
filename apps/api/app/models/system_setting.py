from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from app.models.common import UTCDateTime, utc_now


class SystemSetting(SQLModel, table=True):
    __tablename__ = "system_settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    key: str = Field(index=True, unique=True, max_length=100)
    value: str = Field(sa_type=Text)
    description: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
