from __future__ import annotations

from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.common import (
    CalendarEventStatus,
    DomainEntityType,
    PreferredTimeOfDay,
    ProjectStatus,
    TaskDependencyType,
    TaskPriority,
    TaskStatus,
)
from app.schemas.common import ApiModel, AwareDateTime, TimezoneName
from app.schemas.domain import RecurrenceInput


def _unique_ids(value: list[UUID]) -> list[UUID]:
    if len(set(value)) != len(value):
        raise ValueError("identifier lists cannot contain duplicates")
    return value


class ProjectCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    description_markdown: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    target_start_date: date | None = None
    target_end_date: date | None = None

    @model_validator(mode="after")
    def validate_targets(self) -> Self:
        if (
            self.target_start_date is not None
            and self.target_end_date is not None
            and self.target_end_date < self.target_start_date
        ):
            raise ValueError("target_end_date cannot be before target_start_date")
        return self


class ProjectUpdateRequest(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description_markdown: str | None = None
    status: ProjectStatus | None = None
    target_start_date: date | None = None
    target_end_date: date | None = None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_targets(self) -> Self:
        if (
            "target_start_date" in self.model_fields_set
            and "target_end_date" in self.model_fields_set
            and self.target_start_date is not None
            and self.target_end_date is not None
            and self.target_end_date < self.target_start_date
        ):
            raise ValueError("target_end_date cannot be before target_start_date")
        return self


class RevisionRequest(ApiModel):
    revision: int = Field(ge=1)


class ProjectResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    description_markdown: str | None
    status: ProjectStatus
    target_start_date: date | None
    target_end_date: date | None
    total_tasks: int
    completed_tasks: int
    progress_basis_points: int
    revision: int
    created_at: datetime
    updated_at: datetime


class TaskCreateRequest(ApiModel):
    project_id: UUID | None = None
    parent_task_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description_markdown: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    actual_duration_minutes: int | None = Field(default=None, ge=0)
    earliest_start_at: AwareDateTime | None = None
    due_at: AwareDateTime | None = None
    preferred_time_of_day: PreferredTimeOfDay = PreferredTimeOfDay.ANY
    scheduled_start_at: AwareDateTime | None = None
    scheduled_end_at: AwareDateTime | None = None
    recurrence: RecurrenceInput | None = None
    tag_ids: list[UUID] = Field(default_factory=list)
    commitment_ids: list[UUID] = Field(default_factory=list)

    _validate_tag_ids = field_validator("tag_ids")(_unique_ids)
    _validate_commitment_ids = field_validator("commitment_ids")(_unique_ids)

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        if (self.scheduled_start_at is None) != (self.scheduled_end_at is None):
            raise ValueError("scheduled_start_at and scheduled_end_at must be provided together")
        if (
            self.earliest_start_at is not None
            and self.due_at is not None
            and self.earliest_start_at >= self.due_at
        ):
            raise ValueError("earliest_start_at must be before due_at")
        if (
            self.scheduled_start_at is not None
            and self.scheduled_end_at is not None
            and self.scheduled_end_at <= self.scheduled_start_at
        ):
            raise ValueError("scheduled_end_at must be after scheduled_start_at")
        return self


class TaskUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    project_id: UUID | None = None
    parent_task_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description_markdown: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    actual_duration_minutes: int | None = Field(default=None, ge=0)
    earliest_start_at: AwareDateTime | None = None
    due_at: AwareDateTime | None = None
    preferred_time_of_day: PreferredTimeOfDay | None = None
    scheduled_start_at: AwareDateTime | None = None
    scheduled_end_at: AwareDateTime | None = None
    recurrence: RecurrenceInput | None = None
    tag_ids: list[UUID] | None = None
    commitment_ids: list[UUID] | None = None

    _validate_tag_ids = field_validator("tag_ids")(
        lambda value: _unique_ids(value) if value is not None else value
    )
    _validate_commitment_ids = field_validator("commitment_ids")(
        lambda value: _unique_ids(value) if value is not None else value
    )

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        fields = self.model_fields_set
        if (
            {"earliest_start_at", "due_at"} <= fields
            and self.earliest_start_at is not None
            and self.due_at is not None
            and self.earliest_start_at >= self.due_at
        ):
            raise ValueError("earliest_start_at must be before due_at")
        if {"scheduled_start_at", "scheduled_end_at"} <= fields:
            if (self.scheduled_start_at is None) != (self.scheduled_end_at is None):
                raise ValueError("scheduled interval fields must both be values or both be null")
            if (
                self.scheduled_start_at is not None
                and self.scheduled_end_at is not None
                and self.scheduled_end_at <= self.scheduled_start_at
            ):
                raise ValueError("scheduled_end_at must be after scheduled_start_at")
        return self


class TaskDependencyRequest(ApiModel):
    depends_on_task_id: UUID
    dependency_type: TaskDependencyType = TaskDependencyType.FINISH_TO_START


class TaskDependencyResponse(ApiModel):
    id: UUID
    task_id: UUID
    depends_on_task_id: UUID
    dependency_type: TaskDependencyType
    created_at: datetime


class TaskResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    parent_task_id: UUID | None
    title: str
    description_markdown: str | None
    status: TaskStatus
    priority: TaskPriority
    estimated_duration_minutes: int | None
    actual_duration_minutes: int | None
    earliest_start_at: datetime | None
    due_at: datetime | None
    preferred_time_of_day: PreferredTimeOfDay
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    completed_at: datetime | None
    recurrence_rrule: str | None
    tag_ids: list[UUID]
    commitment_ids: list[UUID]
    dependencies: list[TaskDependencyResponse]
    child_count: int
    overdue: bool
    blocked: bool
    schedulable: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class BulkCompleteItem(ApiModel):
    id: UUID
    revision: int = Field(ge=1)
    actual_duration_minutes: int | None = Field(default=None, ge=0)


class BulkCompleteRequest(ApiModel):
    items: list[BulkCompleteItem] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[BulkCompleteItem]) -> list[BulkCompleteItem]:
        _unique_ids([item.id for item in value])
        return value


class BulkRescheduleItem(ApiModel):
    id: UUID
    revision: int = Field(ge=1)
    scheduled_start_at: AwareDateTime
    scheduled_end_at: AwareDateTime

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.scheduled_end_at <= self.scheduled_start_at:
            raise ValueError("scheduled_end_at must be after scheduled_start_at")
        return self


class BulkRescheduleRequest(ApiModel):
    items: list[BulkRescheduleItem] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[BulkRescheduleItem]) -> list[BulkRescheduleItem]:
        _unique_ids([item.id for item in value])
        return value


class RecurrenceOccurrenceResponse(ApiModel):
    starts_at: datetime
    ends_at: datetime | None = None


class NoteCreateRequest(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    markdown: str = ""
    daily_note_date: date | None = None
    tag_ids: list[UUID] = Field(default_factory=list)
    entity_links: list[DomainLinkRequest] = Field(default_factory=list)
    commitment_ids: list[UUID] = Field(default_factory=list)

    _validate_tag_ids = field_validator("tag_ids")(_unique_ids)
    _validate_commitment_ids = field_validator("commitment_ids")(_unique_ids)


class NoteUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    markdown: str | None = None
    daily_note_date: date | None = None
    tag_ids: list[UUID] | None = None
    entity_links: list[DomainLinkRequest] | None = None
    commitment_ids: list[UUID] | None = None

    _validate_tag_ids = field_validator("tag_ids")(
        lambda value: _unique_ids(value) if value is not None else value
    )
    _validate_commitment_ids = field_validator("commitment_ids")(
        lambda value: _unique_ids(value) if value is not None else value
    )


class NoteLinkRequest(ApiModel):
    target_note_id: UUID
    label: str | None = Field(default=None, max_length=120)


class NoteLinkResponse(ApiModel):
    id: UUID
    source_note_id: UUID
    target_note_id: UUID
    label: str | None
    created_at: datetime


class DomainLinkRequest(ApiModel):
    entity_type: DomainEntityType
    entity_id: UUID
    label: str | None = Field(default=None, max_length=120)


class DomainLinkResponse(ApiModel):
    id: UUID
    entity_type: DomainEntityType
    entity_id: UUID
    label: str | None = None
    created_at: datetime


class NoteResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    title: str
    markdown: str
    daily_note_date: date | None
    tag_ids: list[UUID]
    attachment_ids: list[UUID]
    links: list[NoteLinkResponse]
    backlinks: list[NoteLinkResponse]
    entity_links: list[DomainLinkResponse]
    commitment_ids: list[UUID]
    revision: int
    created_at: datetime
    updated_at: datetime


class AttachmentResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str | None
    entity_type: DomainEntityType
    entity_id: UUID
    revision: int
    created_at: datetime
    updated_at: datetime


class CalendarEventCreateRequest(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    description_markdown: str | None = None
    location: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    status: CalendarEventStatus = CalendarEventStatus.CONFIRMED
    all_day: bool = False
    starts_at: AwareDateTime | None = None
    ends_at: AwareDateTime | None = None
    all_day_start: date | None = None
    all_day_end: date | None = None
    timezone: TimezoneName = "UTC"
    preparation_buffer_minutes: int = Field(default=0, ge=0, le=10_080)
    travel_buffer_minutes: int = Field(default=0, ge=0, le=10_080)
    recovery_buffer_minutes: int = Field(default=0, ge=0, le=10_080)
    recurrence: RecurrenceInput | None = None
    linked_entities: list[DomainLinkRequest] = Field(default_factory=list)
    commitment_ids: list[UUID] = Field(default_factory=list)

    _validate_commitment_ids = field_validator("commitment_ids")(_unique_ids)

    @model_validator(mode="after")
    def validate_time_shape(self) -> Self:
        if self.all_day:
            if self.all_day_start is None or self.all_day_end is None:
                raise ValueError("all-day events require all_day_start and all_day_end")
            if self.all_day_end <= self.all_day_start:
                raise ValueError("all_day_end must be after all_day_start")
            if self.starts_at is not None or self.ends_at is not None:
                raise ValueError("all-day events cannot contain timed fields")
        else:
            if self.starts_at is None or self.ends_at is None:
                raise ValueError("timed events require starts_at and ends_at")
            if self.ends_at <= self.starts_at:
                raise ValueError("ends_at must be after starts_at")
            if self.all_day_start is not None or self.all_day_end is not None:
                raise ValueError("timed events cannot contain all-day fields")
        return self


class CalendarEventUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description_markdown: str | None = None
    location: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    status: CalendarEventStatus | None = None
    preparation_buffer_minutes: int | None = Field(default=None, ge=0, le=10_080)
    travel_buffer_minutes: int | None = Field(default=None, ge=0, le=10_080)
    recovery_buffer_minutes: int | None = Field(default=None, ge=0, le=10_080)
    recurrence: RecurrenceInput | None = None
    linked_entities: list[DomainLinkRequest] | None = None
    commitment_ids: list[UUID] | None = None

    _validate_commitment_ids = field_validator("commitment_ids")(
        lambda value: _unique_ids(value) if value is not None else value
    )


class CalendarMoveRequest(ApiModel):
    revision: int = Field(ge=1)
    starts_at: AwareDateTime | None = None
    all_day_start: date | None = None
    timezone: TimezoneName | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if (self.starts_at is None) == (self.all_day_start is None):
            raise ValueError("provide exactly one of starts_at or all_day_start")
        return self


class CalendarResizeRequest(ApiModel):
    revision: int = Field(ge=1)
    ends_at: AwareDateTime | None = None
    all_day_end: date | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if (self.ends_at is None) == (self.all_day_end is None):
            raise ValueError("provide exactly one of ends_at or all_day_end")
        return self


class CalendarEventResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    title: str
    description_markdown: str | None
    location: str | None
    category: str | None
    status: CalendarEventStatus
    all_day: bool
    starts_at: datetime | None
    ends_at: datetime | None
    all_day_start: date | None
    all_day_end: date | None
    timezone: str
    preparation_buffer_minutes: int
    travel_buffer_minutes: int
    recovery_buffer_minutes: int
    recurrence_rrule: str | None
    external_uid: str | None
    source_sequence: int
    import_fingerprint: str | None
    linked_entities: list[DomainLinkResponse]
    commitment_ids: list[UUID]
    attachment_ids: list[UUID]
    revision: int
    created_at: datetime
    updated_at: datetime


class CalendarConflictOccurrence(ApiModel):
    event_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    effective_starts_at: datetime
    effective_ends_at: datetime
    all_day: bool


class CalendarConflictResponse(ApiModel):
    first: CalendarConflictOccurrence
    second: CalendarConflictOccurrence
