from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Index, UniqueConstraint, text
from sqlmodel import Field

from app.models.common import (
    CurrencyCodeType,
    DomainEntityType,
    EntityBase,
    SoftDeleteEntityBase,
    ThemeMode,
    UTCDateTime,
    WorkspaceEntityBase,
    WorkspaceLinkBase,
    WorkspaceSoftDeleteEntityBase,
    utc_now,
)


class Workspace(SoftDeleteEntityBase, table=True):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_workspaces_name_nonempty"),
        CheckConstraint("revision >= 1", name="ck_workspaces_revision_positive"),
        Index(
            "ux_workspaces_default_active",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1 AND deleted_at IS NULL"),
        ),
    )

    name: str = Field(max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_default: bool = Field(default=False, nullable=False)


class UserPreferences(WorkspaceEntityBase, table=True):
    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_user_preferences_workspace"),
        CheckConstraint("length(currency_code) = 3", name="ck_preferences_currency_length"),
        CheckConstraint(
            "currency_code = upper(currency_code)",
            name="ck_preferences_currency_upper",
        ),
        CheckConstraint("week_starts_on BETWEEN 0 AND 6", name="ck_preferences_week_start"),
        CheckConstraint(
            "session_timeout_minutes BETWEEN 1 AND 1440",
            name="ck_preferences_session_timeout",
        ),
        CheckConstraint("revision >= 1", name="ck_preferences_revision_positive"),
    )

    timezone: str = Field(default="UTC", max_length=64)
    locale: str = Field(default="en", max_length=32)
    currency_code: str = Field(
        default="EUR",
        min_length=3,
        max_length=3,
        sa_type=CurrencyCodeType,
    )
    week_starts_on: int = Field(default=0, ge=0, le=6)
    theme: ThemeMode = Field(default=ThemeMode.SYSTEM)
    session_timeout_minutes: int = Field(default=30, ge=1, le=1_440)


class Tag(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "tags"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_tags_name_nonempty"),
        CheckConstraint("revision >= 1", name="ck_tags_revision_positive"),
        Index(
            "ux_tags_workspace_name_active",
            "workspace_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    name: str = Field(max_length=80)
    color: str | None = Field(default=None, max_length=7)


class TagEntityLink(WorkspaceLinkBase, table=True):
    __tablename__ = "tag_entity_links"
    __table_args__ = (
        UniqueConstraint(
            "tag_id",
            "entity_type",
            "entity_id",
            name="uq_tag_entity_link",
        ),
    )

    tag_id: UUID = Field(foreign_key="tags.id", ondelete="CASCADE", index=True)
    entity_type: DomainEntityType
    entity_id: UUID = Field(index=True)


class Attachment(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint("length(trim(storage_path)) > 0", name="ck_attachments_path_nonempty"),
        CheckConstraint("storage_path NOT LIKE '/%'", name="ck_attachments_path_relative"),
        CheckConstraint("instr(storage_path, '..') = 0", name="ck_attachments_path_no_parent"),
        CheckConstraint("instr(storage_path, ':') = 0", name="ck_attachments_path_no_drive"),
        CheckConstraint("size_bytes >= 0", name="ck_attachments_size_nonnegative"),
        CheckConstraint("revision >= 1", name="ck_attachments_revision_positive"),
        UniqueConstraint("workspace_id", "storage_path", name="uq_attachment_storage_path"),
    )

    storage_path: str = Field(max_length=500)
    original_filename: str = Field(max_length=255)
    media_type: str = Field(max_length=150)
    size_bytes: int = Field(ge=0)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class AttachmentEntityLink(WorkspaceLinkBase, table=True):
    __tablename__ = "attachment_entity_links"
    __table_args__ = (
        UniqueConstraint(
            "attachment_id",
            "entity_type",
            "entity_id",
            name="uq_attachment_entity_link",
        ),
    )

    attachment_id: UUID = Field(
        foreign_key="attachments.id",
        ondelete="CASCADE",
        index=True,
    )
    entity_type: DomainEntityType
    entity_id: UUID = Field(index=True)


class TimelineEvent(EntityBase, table=True):
    __tablename__ = "timeline_events"
    __table_args__ = (
        CheckConstraint("length(trim(action)) > 0", name="ck_timeline_action_nonempty"),
        Index("ix_timeline_workspace_occurred", "workspace_id", "occurred_at", "id"),
    )

    workspace_id: UUID = Field(foreign_key="workspaces.id", ondelete="CASCADE", index=True)
    entity_type: DomainEntityType
    entity_id: UUID = Field(index=True)
    action: str = Field(max_length=50)
    title: str = Field(max_length=255)
    occurred_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    payload: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
