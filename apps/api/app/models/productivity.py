from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Column, Index, Text, UniqueConstraint, text
from sqlmodel import Field

from app.models.common import (
    CalendarEventStatus,
    DomainEntityType,
    PreferredTimeOfDay,
    ProjectStatus,
    RecurrenceFrequency,
    TaskDependencyType,
    TaskPriority,
    TaskStatus,
    UTCDateTime,
    WorkspaceLinkBase,
    WorkspaceSoftDeleteEntityBase,
)


class Project(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_nonempty"),
        CheckConstraint("revision >= 1", name="ck_projects_revision_positive"),
        Index("ix_projects_workspace_status", "workspace_id", "status"),
    )

    name: str = Field(max_length=160)
    description_markdown: str | None = Field(default=None, sa_type=Text)
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    target_start_date: date | None = None
    target_end_date: date | None = None


class Task(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_tasks_title_nonempty"),
        CheckConstraint(
            "estimated_duration_minutes IS NULL OR estimated_duration_minutes >= 0",
            name="ck_tasks_duration_nonnegative",
        ),
        CheckConstraint(
            "scheduled_start_at IS NULL OR scheduled_end_at IS NULL "
            "OR scheduled_end_at > scheduled_start_at",
            name="ck_tasks_scheduled_range",
        ),
        CheckConstraint(
            "(recurrence_frequency IS NULL AND recurrence_interval IS NULL "
            "AND recurrence_days_of_week IS NULL AND recurrence_end_at IS NULL) "
            "OR (recurrence_frequency IS NOT NULL AND recurrence_interval >= 1)",
            name="ck_tasks_recurrence_shape",
        ),
        CheckConstraint("revision >= 1", name="ck_tasks_revision_positive"),
        Index("ix_tasks_workspace_status_due", "workspace_id", "status", "due_at"),
        Index(
            "ix_tasks_workspace_earliest_due",
            "workspace_id",
            "earliest_start_at",
            "due_at",
        ),
    )

    project_id: UUID | None = Field(
        default=None,
        foreign_key="projects.id",
        ondelete="SET NULL",
        index=True,
    )
    parent_task_id: UUID | None = Field(
        default=None,
        foreign_key="tasks.id",
        ondelete="SET NULL",
        index=True,
    )
    title: str = Field(max_length=255)
    description_markdown: str | None = Field(default=None, sa_type=Text)
    status: TaskStatus = Field(default=TaskStatus.TODO)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    actual_duration_minutes: int | None = Field(default=None, ge=0)
    completed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    earliest_start_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    due_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    preferred_time_of_day: PreferredTimeOfDay = Field(default=PreferredTimeOfDay.ANY)
    scheduled_start_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    scheduled_end_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    recurrence_frequency: RecurrenceFrequency | None = Field(default=None)
    recurrence_interval: int | None = Field(default=None, ge=1)
    recurrence_days_of_week: list[int] | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True), nullable=True),
    )
    recurrence_end_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    recurrence_rrule: str | None = Field(default=None, max_length=1000)


class TaskDependency(WorkspaceLinkBase, table=True):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint("task_id <> depends_on_task_id", name="ck_task_dependency_no_self"),
        UniqueConstraint(
            "task_id",
            "depends_on_task_id",
            "dependency_type",
            name="uq_task_dependency",
        ),
    )

    task_id: UUID = Field(foreign_key="tasks.id", ondelete="CASCADE", index=True)
    depends_on_task_id: UUID = Field(
        foreign_key="tasks.id",
        ondelete="CASCADE",
        index=True,
    )
    dependency_type: TaskDependencyType = Field(default=TaskDependencyType.FINISH_TO_START)


class Note(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_notes_title_nonempty"),
        CheckConstraint("revision >= 1", name="ck_notes_revision_positive"),
        Index("ix_notes_workspace_updated", "workspace_id", "updated_at"),
        Index(
            "ux_notes_workspace_daily_date_active",
            "workspace_id",
            "daily_note_date",
            unique=True,
            sqlite_where=text("daily_note_date IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    title: str = Field(max_length=255)
    markdown: str = Field(default="", sa_type=Text)
    daily_note_date: date | None = None


class NoteLink(WorkspaceLinkBase, table=True):
    __tablename__ = "note_links"
    __table_args__ = (
        CheckConstraint("source_note_id <> target_note_id", name="ck_note_link_no_self"),
        UniqueConstraint("source_note_id", "target_note_id", name="uq_note_link"),
    )

    source_note_id: UUID = Field(foreign_key="notes.id", ondelete="CASCADE", index=True)
    target_note_id: UUID = Field(foreign_key="notes.id", ondelete="CASCADE", index=True)
    label: str | None = Field(default=None, max_length=120)


class NoteEntityLink(WorkspaceLinkBase, table=True):
    __tablename__ = "note_entity_links"
    __table_args__ = (
        UniqueConstraint(
            "note_id",
            "entity_type",
            "entity_id",
            name="uq_note_entity_link",
        ),
    )

    note_id: UUID = Field(foreign_key="notes.id", ondelete="CASCADE", index=True)
    entity_type: DomainEntityType
    entity_id: UUID = Field(index=True)
    label: str | None = Field(default=None, max_length=120)


class CalendarEvent(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_events_title_nonempty"),
        CheckConstraint(
            "(all_day = 1 AND all_day_start IS NOT NULL AND all_day_end IS NOT NULL "
            "AND all_day_end > all_day_start AND starts_at IS NULL AND ends_at IS NULL) "
            "OR (all_day = 0 AND starts_at IS NOT NULL AND ends_at IS NOT NULL "
            "AND ends_at > starts_at AND all_day_start IS NULL AND all_day_end IS NULL)",
            name="ck_events_time_shape",
        ),
        CheckConstraint(
            "(recurrence_frequency IS NULL AND recurrence_interval IS NULL "
            "AND recurrence_days_of_week IS NULL AND recurrence_end_at IS NULL) "
            "OR (recurrence_frequency IS NOT NULL AND recurrence_interval >= 1)",
            name="ck_events_recurrence_shape",
        ),
        CheckConstraint("revision >= 1", name="ck_events_revision_positive"),
        CheckConstraint("source_sequence >= 0", name="ck_events_source_sequence_nonnegative"),
        Index("ix_events_workspace_starts", "workspace_id", "starts_at"),
        Index("ix_events_workspace_all_day", "workspace_id", "all_day_start"),
        Index(
            "ux_events_workspace_external_uid_active",
            "workspace_id",
            "external_uid",
            unique=True,
            sqlite_where=text("external_uid IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "ix_events_workspace_import_fingerprint",
            "workspace_id",
            "import_fingerprint",
        ),
    )

    title: str = Field(max_length=255)
    description_markdown: str | None = Field(default=None, sa_type=Text)
    location: str | None = Field(default=None, max_length=255)
    status: CalendarEventStatus = Field(default=CalendarEventStatus.CONFIRMED)
    all_day: bool = Field(default=False)
    starts_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    ends_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    all_day_start: date | None = None
    all_day_end: date | None = None
    timezone: str = Field(default="UTC", max_length=64)
    recurrence_frequency: RecurrenceFrequency | None = Field(default=None)
    recurrence_interval: int | None = Field(default=None, ge=1)
    recurrence_days_of_week: list[int] | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True), nullable=True),
    )
    recurrence_end_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    recurrence_rrule: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=120)
    preparation_buffer_minutes: int = Field(
        default=0,
        ge=0,
        sa_column_kwargs={"server_default": "0"},
    )
    travel_buffer_minutes: int = Field(
        default=0,
        ge=0,
        sa_column_kwargs={"server_default": "0"},
    )
    recovery_buffer_minutes: int = Field(
        default=0,
        ge=0,
        sa_column_kwargs={"server_default": "0"},
    )
    external_uid: str | None = Field(default=None, max_length=255)
    source_sequence: int = Field(default=0, ge=0)
    import_fingerprint: str | None = Field(default=None, max_length=64)


class CalendarEventEntityLink(WorkspaceLinkBase, table=True):
    __tablename__ = "calendar_event_entity_links"
    __table_args__ = (
        UniqueConstraint(
            "calendar_event_id",
            "entity_type",
            "entity_id",
            name="uq_calendar_event_entity_link",
        ),
    )

    calendar_event_id: UUID = Field(
        foreign_key="calendar_events.id",
        ondelete="CASCADE",
        index=True,
    )
    entity_type: DomainEntityType
    entity_id: UUID = Field(index=True)
