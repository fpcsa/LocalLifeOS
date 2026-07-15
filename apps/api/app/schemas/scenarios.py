from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models import DomainEntityType, ScenarioOperation, ScenarioStatus
from app.schemas.common import ApiModel

SUPPORTED_SCENARIO_ENTITY_TYPES = frozenset(
    {
        DomainEntityType.TASK,
        DomainEntityType.CALENDAR_EVENT,
        DomainEntityType.PLANNED_TRANSACTION,
        DomainEntityType.COMMITMENT,
        DomainEntityType.GOAL,
    }
)


class ScenarioCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    description_markdown: str | None = None


class ScenarioUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description_markdown: str | None = None


class ScenarioRevisionRequest(ApiModel):
    revision: int = Field(ge=1)


class ScenarioChangeCreateRequest(ApiModel):
    entity_type: DomainEntityType
    entity_id: UUID
    operation: ScenarioOperation
    changes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, value: DomainEntityType) -> DomainEntityType:
        if value not in SUPPORTED_SCENARIO_ENTITY_TYPES:
            supported = ", ".join(sorted(item.value for item in SUPPORTED_SCENARIO_ENTITY_TYPES))
            raise ValueError(f"scenario changes support: {supported}")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> ScenarioChangeCreateRequest:
        if self.operation == ScenarioOperation.DELETE and self.changes:
            raise ValueError("delete scenario changes cannot include field changes")
        if self.operation != ScenarioOperation.DELETE and not self.changes:
            raise ValueError("create and update scenario changes require field changes")
        return self


class ScenarioChangeUpdateRequest(ApiModel):
    revision: int = Field(ge=1)
    changes: dict[str, Any] = Field(min_length=1)


class ScenarioChangeResponse(ApiModel):
    id: UUID
    scenario_id: UUID
    entity_type: DomainEntityType
    entity_id: UUID
    operation: ScenarioOperation
    changes: dict[str, Any]
    expected_revision: int | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ScenarioResponse(ApiModel):
    id: UUID
    workspace_id: UUID
    name: str
    description_markdown: str | None
    status: ScenarioStatus
    base_revision: int
    change_count: int
    revision: int
    created_at: datetime
    updated_at: datetime


class ScenarioCurrencyProjection(ApiModel):
    currency: str
    projected_cash_flow_minor: int
    lowest_balance_minor: int
    financial_buffer_violations: int


class ScenarioMetrics(ApiModel):
    currencies: list[ScenarioCurrencyProjection]
    time_required_minutes: int
    schedule_conflicts: int
    goal_progress_basis_points: int
    unscheduled_tasks: int
    commitment_status: dict[str, int]


class ScenarioMetricDelta(ApiModel):
    projected_cash_flow_minor: dict[str, int]
    lowest_balance_minor: dict[str, int]
    financial_buffer_violations: int
    time_required_minutes: int
    schedule_conflicts: int
    goal_progress_basis_points: int
    unscheduled_tasks: int
    commitment_status: dict[str, int]


class ScenarioPlanField(ApiModel):
    field: str
    before: Any | None = None
    after: Any | None = None


class ScenarioPlanStep(ApiModel):
    change_id: UUID
    operation: ScenarioOperation
    entity_type: DomainEntityType
    entity_id: UUID
    title: str
    expected_revision: int | None
    fields: list[ScenarioPlanField]


class ScenarioPreviewResponse(ApiModel):
    scenario: ScenarioResponse
    changes: list[ScenarioChangeResponse]
    baseline: ScenarioMetrics
    projected: ScenarioMetrics
    differences: ScenarioMetricDelta
    exact_change_plan: list[ScenarioPlanStep]
    stale: bool
    stale_reasons: list[str]
    preview_fingerprint: str
    assumptions: list[str]
    calculated_at: datetime


class ScenarioCompareRequest(ApiModel):
    scenario_ids: list[UUID] = Field(min_length=2, max_length=3)

    @field_validator("scenario_ids")
    @classmethod
    def unique_scenarios(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("scenario_ids cannot contain duplicates")
        return value


class ScenarioCompareResponse(ApiModel):
    previews: list[ScenarioPreviewResponse]


class ScenarioAcceptRequest(ApiModel):
    revision: int = Field(ge=1)
    preview_fingerprint: str = Field(min_length=64, max_length=64)


class ScenarioAcceptResponse(ApiModel):
    scenario: ScenarioResponse
    applied_steps: list[ScenarioPlanStep]
    accepted_at: datetime
