from __future__ import annotations

import re
from datetime import date
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.common import (
    CommitmentEntityType,
    DomainEntityType,
    RecurrenceFrequency,
    ScenarioOperation,
    TaskPriority,
    TaskStatus,
    TransactionType,
)
from app.schemas.common import ApiModel, AwareDateTime, CurrencyCode, TimezoneName
from app.utils.recurrence import canonicalize_rrule

HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class RecurrenceInput(ApiModel):
    rrule: str | None = None
    frequency: RecurrenceFrequency | None = None
    interval: int = Field(default=1, ge=1, le=999)
    days_of_week: list[int] | None = None
    end_at: AwareDateTime | None = None

    @field_validator("rrule")
    @classmethod
    def validate_rrule(cls, value: str | None) -> str | None:
        return canonicalize_rrule(value) if value is not None else None

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("days_of_week cannot be empty")
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("days_of_week values must be between 0 and 6")
        if len(set(value)) != len(value):
            raise ValueError("days_of_week values must be unique")
        return sorted(value)

    @model_validator(mode="after")
    def validate_frequency_shape(self) -> RecurrenceInput:
        if (self.rrule is None) == (self.frequency is None):
            raise ValueError("provide exactly one of rrule or frequency")
        if self.rrule is not None:
            if self.interval != 1 or self.days_of_week is not None or self.end_at is not None:
                raise ValueError("rrule cannot be combined with explicit recurrence fields")
            return self
        if self.frequency == RecurrenceFrequency.WEEKLY and self.days_of_week is None:
            raise ValueError("weekly recurrence requires days_of_week")
        if self.frequency != RecurrenceFrequency.WEEKLY and self.days_of_week is not None:
            raise ValueError("days_of_week is only valid for weekly recurrence")
        return self


class TaskCreate(ApiModel):
    project_id: UUID | None = None
    parent_task_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description_markdown: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    due_at: AwareDateTime | None = None
    scheduled_start_at: AwareDateTime | None = None
    scheduled_end_at: AwareDateTime | None = None
    recurrence: RecurrenceInput | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> TaskCreate:
        if (self.scheduled_start_at is None) != (self.scheduled_end_at is None):
            raise ValueError("scheduled_start_at and scheduled_end_at must be provided together")
        if (
            self.scheduled_start_at is not None
            and self.scheduled_end_at is not None
            and self.scheduled_end_at <= self.scheduled_start_at
        ):
            raise ValueError("scheduled_end_at must be after scheduled_start_at")
        return self


class TaskDependencyCreate(ApiModel):
    task_id: UUID
    depends_on_task_id: UUID

    @model_validator(mode="after")
    def prevent_self_dependency(self) -> TaskDependencyCreate:
        if self.task_id == self.depends_on_task_id:
            raise ValueError("a task cannot depend on itself")
        return self


class NoteLinkCreate(ApiModel):
    source_note_id: UUID
    target_note_id: UUID
    label: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def prevent_self_link(self) -> NoteLinkCreate:
        if self.source_note_id == self.target_note_id:
            raise ValueError("a note cannot link to itself")
        return self


class CalendarEventCreate(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    description_markdown: str | None = None
    location: str | None = Field(default=None, max_length=255)
    all_day: bool = False
    starts_at: AwareDateTime | None = None
    ends_at: AwareDateTime | None = None
    all_day_start: date | None = None
    all_day_end: date | None = None
    timezone: TimezoneName = "UTC"
    recurrence: RecurrenceInput | None = None

    @model_validator(mode="after")
    def validate_event_time(self) -> CalendarEventCreate:
        if self.all_day:
            if self.all_day_start is None or self.all_day_end is None:
                raise ValueError("all-day events require all_day_start and all_day_end")
            if self.all_day_end <= self.all_day_start:
                raise ValueError("all_day_end must be after all_day_start")
            if self.starts_at is not None or self.ends_at is not None:
                raise ValueError("all-day events cannot include timed fields")
        else:
            if self.starts_at is None or self.ends_at is None:
                raise ValueError("timed events require starts_at and ends_at")
            if self.ends_at <= self.starts_at:
                raise ValueError("ends_at must be after starts_at")
            if self.all_day_start is not None or self.all_day_end is not None:
                raise ValueError("timed events cannot include all-day date fields")
        return self


class TransactionCreate(ApiModel):
    account_id: UUID
    transfer_account_id: UUID | None = None
    category_id: UUID | None = None
    transaction_type: TransactionType
    amount_minor: int = Field(gt=0)
    currency_code: CurrencyCode
    occurred_at: AwareDateTime
    payee: str | None = Field(default=None, max_length=255)
    note: str | None = None
    external_id: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_transfer_shape(self) -> TransactionCreate:
        if self.transaction_type == TransactionType.TRANSFER:
            if self.transfer_account_id is None:
                raise ValueError("transfers require transfer_account_id")
            if self.transfer_account_id == self.account_id:
                raise ValueError("transfer accounts must be different")
            if self.category_id is not None:
                raise ValueError("transfers cannot have a transaction category")
        elif self.transfer_account_id is not None:
            raise ValueError("only transfers can specify transfer_account_id")
        return self


class BudgetCreate(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    start_date: date
    end_date: date | None = None
    currency_code: CurrencyCode

    @model_validator(mode="after")
    def validate_date_range(self) -> BudgetCreate:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class CommitmentCreate(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    starts_at: AwareDateTime | None = None
    ends_at: AwareDateTime | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    planned_cost_minor: int | None = Field(default=None, ge=0)
    currency_code: CurrencyCode | None = None

    @model_validator(mode="after")
    def validate_commitment_shape(self) -> CommitmentCreate:
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be after starts_at")
        if (self.planned_cost_minor is None) != (self.currency_code is None):
            raise ValueError("planned_cost_minor and currency_code must be provided together")
        return self


class CommitmentLinkCreate(ApiModel):
    commitment_id: UUID
    entity_type: CommitmentEntityType
    entity_id: UUID
    role: str | None = Field(default=None, max_length=80)


class AttachmentCreate(ApiModel):
    storage_path: str = Field(min_length=1, max_length=500)
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=150)
    size_bytes: int = Field(ge=0)
    sha256: str | None = None

    @field_validator("storage_path")
    @classmethod
    def validate_storage_path(cls, value: str) -> str:
        if "\\" in value or ":" in value:
            raise ValueError("storage_path must use a relative POSIX path")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ValueError("storage_path cannot be absolute or traverse parent directories")
        return path.as_posix()

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is not None and SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class ScenarioChangeCreate(ApiModel):
    scenario_id: UUID
    entity_type: DomainEntityType
    entity_id: UUID
    operation: ScenarioOperation
    changes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_changes(self) -> ScenarioChangeCreate:
        if self.operation == ScenarioOperation.DELETE and self.changes:
            raise ValueError("delete scenario changes cannot include a patch")
        if self.operation != ScenarioOperation.DELETE and not self.changes:
            raise ValueError("create and update scenario changes require a patch")
        return self
