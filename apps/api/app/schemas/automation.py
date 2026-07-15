from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from app.models import (
    AutomationActionType,
    AutomationExecutionStatus,
    AutomationTriggerType,
    DomainEntityType,
    NotificationKind,
    TaskPriority,
    TransactionType,
)
from app.schemas.common import ApiModel, CurrencyCode, TimezoneName

JsonScalar = str | int | float | bool | None


class AutomationOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    IN = "in"


class AutomationScheduleFrequency(StrEnum):
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"


class AutomationCondition(ApiModel):
    field: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    operator: AutomationOperator = AutomationOperator.EQUALS
    value: JsonScalar | list[JsonScalar]


class AutomationSchedule(ApiModel):
    frequency: AutomationScheduleFrequency
    timezone: TimezoneName = "UTC"
    interval_minutes: int | None = Field(default=None, ge=1, le=43_200)
    local_time: time | None = None
    weekdays: list[int] = Field(default_factory=list, max_length=7)

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        if len(self.weekdays) != len(set(self.weekdays)) or any(
            value < 0 or value > 6 for value in self.weekdays
        ):
            raise ValueError("weekdays must contain unique values from 0 through 6")
        if self.frequency == AutomationScheduleFrequency.INTERVAL:
            if self.interval_minutes is None:
                raise ValueError("interval schedules require interval_minutes")
            if self.local_time is not None or self.weekdays:
                raise ValueError("interval schedules cannot use local_time or weekdays")
        elif self.local_time is None:
            raise ValueError("daily and weekly schedules require local_time")
        elif self.frequency == AutomationScheduleFrequency.WEEKLY and not self.weekdays:
            raise ValueError("weekly schedules require at least one weekday")
        return self


class AutomationTrigger(ApiModel):
    type: AutomationTriggerType
    conditions: list[AutomationCondition] = Field(default_factory=list, max_length=20)
    schedule: AutomationSchedule | None = None
    lookahead_minutes: int | None = Field(default=None, ge=1, le=10_080)

    @model_validator(mode="after")
    def validate_trigger(self) -> Self:
        if self.type == AutomationTriggerType.RECURRING_SCHEDULE:
            if self.schedule is None:
                raise ValueError("recurring schedule triggers require schedule")
        elif self.schedule is not None:
            raise ValueError("schedule is only valid for recurring schedule triggers")
        if self.type == AutomationTriggerType.EVENT_APPROACHING:
            if self.lookahead_minutes is None:
                self.lookahead_minutes = 1_440
        elif self.lookahead_minutes is not None:
            raise ValueError("lookahead_minutes is only valid for event approaching triggers")
        return self


class AutomationAction(ApiModel):
    type: AutomationActionType
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=10_000)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_in_days: int | None = Field(default=None, ge=0, le=3_650)
    account_id: UUID | None = None
    category_id: UUID | None = None
    transaction_type: TransactionType | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    currency_code: CurrencyCode | None = None
    days_from_trigger: int = Field(default=0, ge=0, le=3_650)
    tag_id: UUID | None = None
    target_entity_type: DomainEntityType | None = None
    target_entity_id: UUID | None = None

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        titled = {
            AutomationActionType.CREATE_TASK,
            AutomationActionType.CREATE_NOTE,
            AutomationActionType.CREATE_NOTIFICATION,
            AutomationActionType.REQUEST_LOCAL_BACKUP_REMINDER,
        }
        if self.type in titled and self.title is None:
            raise ValueError(f"{self.type.value} requires title")
        if self.type == AutomationActionType.CREATE_PLANNED_TRANSACTION:
            required = (
                self.account_id,
                self.transaction_type,
                self.amount_minor,
                self.currency_code,
            )
            if any(value is None for value in required):
                raise ValueError(
                    "planned transaction actions require account, type, amount, and currency"
                )
            if self.transaction_type == TransactionType.TRANSFER:
                raise ValueError("automation cannot create transfer plans")
        if self.type == AutomationActionType.ADD_TAG and self.tag_id is None:
            raise ValueError("add tag actions require tag_id")
        if (self.target_entity_type is None) != (self.target_entity_id is None):
            raise ValueError("target entity type and ID must be supplied together")
        return self


class AutomationRuleCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    enabled: bool = True
    trigger: AutomationTrigger
    action: AutomationAction


class AutomationRuleUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    enabled: bool | None = None
    trigger: AutomationTrigger | None = None
    action: AutomationAction | None = None


class AutomationRuleResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    enabled: bool
    trigger: AutomationTrigger
    action: AutomationAction
    last_run_at: datetime | None
    next_run_at: datetime | None
    execution_count: int = 0
    revision: int
    created_at: datetime
    updated_at: datetime


class AutomationPreviewRequest(ApiModel):
    context: dict[str, JsonScalar] = Field(default_factory=dict)
    source_key: str = Field(default="manual-preview", min_length=1, max_length=500)


class AutomationActionPreview(ApiModel):
    type: AutomationActionType
    description: str
    payload: dict[str, object]


class AutomationPreviewResponse(ApiModel):
    rule_id: UUID
    matched: bool
    condition_results: list[str]
    action: AutomationActionPreview | None
    writes_performed: bool = False


class AutomationExecutionResponse(ApiModel):
    id: UUID
    rule_id: UUID
    trigger_type: AutomationTriggerType
    action_type: AutomationActionType
    status: AutomationExecutionStatus
    source_key: str
    trigger_context: dict[str, object]
    action_result: dict[str, object]
    error: str | None
    completed_at: datetime | None
    created_at: datetime


class NotificationResponse(ApiModel):
    id: UUID
    kind: NotificationKind
    title: str
    message: str | None
    read_at: datetime | None
    created_at: datetime


class SchedulerStatusResponse(ApiModel):
    running: bool
    scheduled_rule_ids: list[UUID]
    next_wakeup_at: datetime | None
