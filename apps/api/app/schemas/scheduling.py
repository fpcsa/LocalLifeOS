from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models import PreferredTimeOfDay, TaskPriority
from app.schemas.common import ApiModel, AwareDateTime

MAX_PLANNING_DAYS = 30


class SchedulingSolverStatus(StrEnum):
    NOT_RUN = "not_run"
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    MODEL_INVALID = "model_invalid"
    UNKNOWN = "unknown"


class DeadlineRiskLevel(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    MISSED = "missed"
    UNSCHEDULED = "unscheduled"
    NOT_APPLICABLE = "not_applicable"


class SchedulingConflictKind(StrEnum):
    CALENDAR_EVENT = "calendar_event"
    EXISTING_TASK = "existing_task"
    SOFT_PREFERENCE = "soft_preference"


class UnscheduledReasonCode(StrEnum):
    ALREADY_SCHEDULED = "already_scheduled"
    INACTIVE_TASK = "inactive_task"
    DURATION_MISSING = "duration_missing"
    OUTSIDE_HORIZON = "outside_horizon"
    DEADLINE_BEFORE_EARLIEST_START = "deadline_before_earliest_start"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    DEPENDENCY_ORDER_INFEASIBLE = "dependency_order_infeasible"
    HARD_CALENDAR_CONFLICT = "hard_calendar_conflict"
    INSUFFICIENT_CONTIGUOUS_CAPACITY = "insufficient_contiguous_capacity"
    INSUFFICIENT_TOTAL_CAPACITY = "insufficient_total_capacity"
    DAILY_WORKLOAD_LIMIT = "daily_workload_limit"
    SOFT_OBJECTIVE_TRADEOFF = "soft_objective_tradeoff"
    SOLVER_TIMEOUT = "solver_timeout"
    MODEL_INVALID = "model_invalid"


class AvailabilityWindowInput(ApiModel):
    starts_at: AwareDateTime
    ends_at: AwareDateTime

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class WeeklyAvailabilityWindow(ApiModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_wall_times(self) -> Self:
        if self.start_time.tzinfo is not None or self.end_time.tzinfo is not None:
            raise ValueError("weekly availability times must be local wall times without offsets")
        if self.start_time == self.end_time:
            raise ValueError("weekly availability start and end cannot be equal")
        return self


def default_working_hours() -> list[WeeklyAvailabilityWindow]:
    return [
        WeeklyAvailabilityWindow(
            weekday=weekday,
            start_time=time(hour=9),
            end_time=time(hour=17),
        )
        for weekday in range(5)
    ]


class SchedulingObjectiveWeights(ApiModel):
    scheduled_task: int = Field(default=1_000_000, ge=0, le=10_000_000)
    priority: int = Field(default=100_000, ge=0, le=10_000_000)
    preferred_time: int = Field(default=10_000, ge=0, le=10_000_000)
    earlier_start: int = Field(default=1, ge=0, le=10_000)
    fragmentation: int = Field(default=1, ge=0, le=10_000)

    @model_validator(mode="after")
    def require_an_objective(self) -> Self:
        if not any(self.model_dump().values()):
            raise ValueError("at least one scheduling objective weight must be positive")
        return self


class SchedulingPolicyInput(ApiModel):
    working_hours: list[WeeklyAvailabilityWindow] = Field(
        default_factory=default_working_hours,
        max_length=28,
    )
    personal_availability_windows: list[AvailabilityWindowInput] = Field(
        default_factory=list,
        max_length=200,
    )
    minimum_focus_block_minutes: int = Field(default=30, ge=5, le=480)
    maximum_scheduled_minutes_per_day: int = Field(default=480, ge=30, le=1_440)
    objective_weights: SchedulingObjectiveWeights = Field(
        default_factory=SchedulingObjectiveWeights
    )

    @field_validator("working_hours")
    @classmethod
    def unique_working_hours(
        cls,
        value: list[WeeklyAvailabilityWindow],
    ) -> list[WeeklyAvailabilityWindow]:
        keys = [(item.weekday, item.start_time, item.end_time) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("working_hours cannot contain duplicate windows")
        return value


class SchedulingScopeInput(ApiModel):
    planning_start_at: AwareDateTime
    planning_end_at: AwareDateTime
    policy: SchedulingPolicyInput = Field(default_factory=SchedulingPolicyInput)
    solver_time_limit_seconds: float = Field(default=2.0, ge=0.001, le=30.0)

    @model_validator(mode="after")
    def validate_horizon(self) -> Self:
        if self.planning_end_at <= self.planning_start_at:
            raise ValueError("planning_end_at must be after planning_start_at")
        if self.planning_end_at - self.planning_start_at > timedelta(days=MAX_PLANNING_DAYS):
            raise ValueError(f"planning horizon cannot exceed {MAX_PLANNING_DAYS} days")
        return self


class SchedulingPreviewRequest(SchedulingScopeInput):
    task_ids: list[UUID] = Field(min_length=1, max_length=100)
    commitment_id: UUID | None = None

    @field_validator("task_ids")
    @classmethod
    def unique_task_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("task_ids cannot contain duplicates")
        return value


class SchedulingApplyRequest(ApiModel):
    preview_id: UUID
    task_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("task_ids")
    @classmethod
    def unique_task_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("task_ids cannot contain duplicates")
        return value


class SchedulingEntityReference(ApiModel):
    entity_type: str
    entity_id: UUID


class SchedulingReason(ApiModel):
    code: UnscheduledReasonCode
    message: str
    contributing_entities: list[SchedulingEntityReference] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class SuggestedTaskPlacement(ApiModel):
    task_id: UUID
    title: str
    expected_revision: int
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    priority: TaskPriority
    deadline_at: datetime | None
    preferred_time_of_day: PreferredTimeOfDay
    preference_satisfied: bool


class UnscheduledTask(ApiModel):
    task_id: UUID
    title: str
    duration_minutes: int | None
    priority: TaskPriority
    deadline_at: datetime | None
    reasons: list[SchedulingReason] = Field(min_length=1)


class SchedulingConflict(ApiModel):
    kind: SchedulingConflictKind
    hard: bool
    message: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    task_id: UUID | None = None
    entity: SchedulingEntityReference | None = None


class CapacityDay(ApiModel):
    local_date: date
    raw_free_minutes: int
    eligible_schedulable_minutes: int
    focus_capable_minutes: int
    already_committed_minutes: int
    existing_scheduled_task_minutes: int
    suggested_task_minutes: int
    remaining_capacity_minutes: int
    overload_minutes: int


class CapacityWeek(ApiModel):
    week_start_date: date
    week_end_date: date
    raw_free_minutes: int
    eligible_schedulable_minutes: int
    focus_capable_minutes: int
    already_committed_minutes: int
    suggested_task_minutes: int
    remaining_capacity_minutes: int
    overload_minutes: int


class CapacityReport(ApiModel):
    timezone: str
    planning_start_at: datetime
    planning_end_at: datetime
    commitment_id: UUID | None
    required_task_minutes: int
    available_focus_minutes: int
    remaining_capacity_minutes: int
    required_minus_available_minutes: int
    days: list[CapacityDay]
    weeks: list[CapacityWeek]
    assumptions: list[str]


class DeadlineRisk(ApiModel):
    task_id: UUID
    deadline_at: datetime | None
    level: DeadlineRiskLevel
    scheduled_end_at: datetime | None
    slack_minutes: int | None
    explanation: str


class SchedulingObjectiveBreakdown(ApiModel):
    scheduled_task_reward: int
    priority_reward: int
    preferred_time_reward: int
    earlier_start_penalty: int
    fragmentation_penalty: int
    total: int
    best_bound: float | None


class SchedulingPreviewResponse(ApiModel):
    preview_id: UUID
    created_at: datetime
    expires_at: datetime
    commitment_id: UUID | None
    timezone: str
    planning_start_at: datetime
    planning_end_at: datetime
    solver_status: SchedulingSolverStatus
    optimality_proven: bool
    solve_duration_ms: int
    source_fingerprint: str
    placements: list[SuggestedTaskPlacement]
    unscheduled_tasks: list[UnscheduledTask]
    conflicts: list[SchedulingConflict]
    capacity: CapacityReport
    deadline_risks: list[DeadlineRisk]
    assumptions: list[str]
    objective: SchedulingObjectiveBreakdown


class SchedulingExplanationResponse(ApiModel):
    preview_id: UUID
    solver_status: SchedulingSolverStatus
    optimality_proven: bool
    unscheduled_tasks: list[UnscheduledTask]
    conflicts: list[SchedulingConflict]
    deadline_risks: list[DeadlineRisk]
    assumptions: list[str]
    objective: SchedulingObjectiveBreakdown


class SchedulingApplyResponse(ApiModel):
    preview_id: UUID
    applied_at: datetime
    placements: list[SuggestedTaskPlacement]
