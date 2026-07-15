from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from app.models import CommitmentEntityType, CommitmentStatus
from app.schemas.common import ApiModel, AwareDateTime, CurrencyCode


class AssessmentLevel(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


class WarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class UnifiedTimelineEntityType(StrEnum):
    TASK = "task"
    CALENDAR_EVENT = "calendar_event"
    NOTE = "note"
    TRANSACTION = "transaction"
    PLANNED_TRANSACTION = "planned_transaction"
    SAVINGS_GOAL = "savings_goal"
    GOAL = "goal"
    COMMITMENT = "commitment"


class CommitmentCreateRequest(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    description_markdown: str | None = None
    status: CommitmentStatus = CommitmentStatus.DRAFT
    category: str | None = Field(default=None, min_length=1, max_length=120)
    target_start_at: AwareDateTime | None = None
    target_end_at: AwareDateTime | None = None
    decision_deadline_at: AwareDateTime | None = None
    time_capacity_requirement_minutes: int | None = Field(default=None, ge=0)
    planned_cost_minor: int | None = Field(default=None, ge=0)
    financial_buffer_requirement_minor: int | None = Field(default=None, ge=0)
    currency_code: CurrencyCode | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.status == CommitmentStatus.ARCHIVED:
            raise ValueError("use the archive action to archive a commitment")
        if (
            self.target_start_at is not None
            and self.target_end_at is not None
            and self.target_end_at <= self.target_start_at
        ):
            raise ValueError("target_end_at must be after target_start_at")
        if (
            self.decision_deadline_at is not None
            and self.target_end_at is not None
            and self.decision_deadline_at > self.target_end_at
        ):
            raise ValueError("decision_deadline_at cannot be after target_end_at")
        has_money = (
            self.planned_cost_minor is not None
            or self.financial_buffer_requirement_minor is not None
        )
        if has_money != (self.currency_code is not None):
            raise ValueError(
                "money fields require currency_code, and currency_code requires a money field"
            )
        return self


class CommitmentUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description_markdown: str | None = None
    status: CommitmentStatus | None = None
    category: str | None = Field(default=None, min_length=1, max_length=120)
    target_start_at: AwareDateTime | None = None
    target_end_at: AwareDateTime | None = None
    decision_deadline_at: AwareDateTime | None = None
    time_capacity_requirement_minutes: int | None = Field(default=None, ge=0)
    planned_cost_minor: int | None = Field(default=None, ge=0)
    financial_buffer_requirement_minor: int | None = Field(default=None, ge=0)
    currency_code: CurrencyCode | None = None


class CommitmentRevisionRequest(ApiModel):
    revision: int = Field(ge=1)


class CommitmentLinkCreateRequest(ApiModel):
    entity_type: CommitmentEntityType
    entity_id: UUID
    role: str | None = Field(default=None, min_length=1, max_length=80)


class CommitmentLinkResponse(ApiModel):
    id: UUID
    commitment_id: UUID
    entity_type: CommitmentEntityType
    entity_id: UUID
    role: str | None
    created_at: datetime


class CommitmentResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    title: str
    description_markdown: str | None
    status: CommitmentStatus
    category: str | None
    target_start_at: datetime | None
    target_end_at: datetime | None
    decision_deadline_at: datetime | None
    time_capacity_requirement_minutes: int | None
    planned_cost_minor: int | None
    financial_buffer_requirement_minor: int | None
    currency_code: str | None
    links: list[CommitmentLinkResponse]
    revision: int
    created_at: datetime
    updated_at: datetime


class AssessmentEntityReference(ApiModel):
    entity_type: str
    entity_id: UUID


class CommitmentWarning(ApiModel):
    code: str
    severity: WarningSeverity
    message: str
    contributing_entities: list[AssessmentEntityReference] = Field(min_length=1)
    details: dict[str, int | str | bool | None] = Field(default_factory=dict)


class SuggestedAction(ApiModel):
    code: str
    title: str
    reason: str
    contributing_entities: list[AssessmentEntityReference] = Field(min_length=1)


class CurrencyImpact(ApiModel):
    currency: str
    planned_cost_minor: int
    actual_cost_minor: int
    expected_income_minor: int
    ledger_balance_minor: int
    projected_available_minor: int
    required_financial_buffer_minor: int
    financial_buffer_violation: bool


class TimeImpact(ApiModel):
    required_task_duration_minutes: int
    scheduled_task_duration_minutes: int
    preparation_minutes: int
    travel_minutes: int
    recovery_minutes: int
    time_capacity_requirement_minutes: int
    unscheduled_required_work_minutes: int
    unscheduled_task_ids: list[UUID]


class DependencyImpact(ApiModel):
    missing_dependency_ids: list[UUID]
    blocked_task_ids: list[UUID]


class CalendarConflictImpact(ApiModel):
    first_event_id: UUID
    second_event_id: UUID
    first_effective_start: datetime
    first_effective_end: datetime
    second_effective_start: datetime
    second_effective_end: datetime


class BudgetImpact(ApiModel):
    budget_id: UUID
    name: str
    currency: str
    total_limit_minor: int
    total_actual_minor: int
    total_planned_minor: int
    commitment_planned_minor: int
    remaining_after_planned_minor: int
    violation: bool


class SavingsGoalImpact(ApiModel):
    savings_goal_id: UUID
    name: str
    currency: str
    target_minor: int
    current_minor: int
    commitment_outflow_minor: int
    projected_current_minor: int
    projected_remaining_minor: int
    delayed: bool


class DeadlineImpact(ApiModel):
    decision_deadline_at: datetime | None
    target_end_at: datetime | None
    decision_deadline_passed: bool
    target_deadline_passed: bool
    days_until_decision: int | None
    days_until_target: int | None


class CommitmentImpactResponse(ApiModel):
    commitment_id: UUID
    currencies: list[CurrencyImpact]
    time: TimeImpact
    dependencies: DependencyImpact
    calendar_conflicts: list[CalendarConflictImpact]
    budgets: list[BudgetImpact]
    savings_goals: list[SavingsGoalImpact]
    deadline: DeadlineImpact
    missing_link_targets: list[AssessmentEntityReference]


class AssessmentComponent(ApiModel):
    status: AssessmentLevel
    summary: str
    warning_codes: list[str] = Field(default_factory=list)


class CommitmentAssessmentResponse(ApiModel):
    commitment: CommitmentResponse
    impact: CommitmentImpactResponse
    time_capacity_status: AssessmentComponent
    financial_capacity_status: AssessmentComponent
    dependency_status: AssessmentComponent
    schedule_conflict_status: AssessmentComponent
    goal_impact_status: AssessmentComponent
    deadline_status: AssessmentComponent
    overall_status: AssessmentLevel
    warnings: list[CommitmentWarning]
    assumptions: list[str]
    suggested_actions: list[SuggestedAction]
    calculated_at: datetime


class CommitmentWarningsResponse(ApiModel):
    commitment_id: UUID
    overall_status: AssessmentLevel
    warnings: list[CommitmentWarning]
    suggested_actions: list[SuggestedAction]
    assumptions: list[str]
    calculated_at: datetime


class UnifiedTimelineItem(ApiModel):
    item_id: str
    entity_type: UnifiedTimelineEntityType
    entity_id: UUID
    occurred_at: datetime
    kind: str
    title: str
    summary: str | None = None
    status: str | None = None
    sensitive: bool = False
    related_entities: list[AssessmentEntityReference] = Field(default_factory=list)
