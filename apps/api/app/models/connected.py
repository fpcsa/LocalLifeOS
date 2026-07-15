from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Index, Text, UniqueConstraint
from sqlmodel import Field

from app.models.common import (
    CommitmentEntityType,
    CommitmentStatus,
    CurrencyCodeType,
    DomainEntityType,
    GoalStatus,
    ScenarioOperation,
    ScenarioStatus,
    UTCDateTime,
    WorkspaceEntityBase,
    WorkspaceLinkBase,
    WorkspaceSoftDeleteEntityBase,
)


class Goal(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_goals_title_nonempty"),
        CheckConstraint("progress_basis_points BETWEEN 0 AND 10000", name="ck_goals_progress"),
        CheckConstraint("revision >= 1", name="ck_goals_revision_positive"),
        Index("ix_goals_workspace_status", "workspace_id", "status"),
    )

    title: str = Field(max_length=255)
    description_markdown: str | None = Field(default=None, sa_type=Text)
    status: GoalStatus = Field(default=GoalStatus.ACTIVE)
    progress_basis_points: int = Field(default=0, ge=0, le=10_000)
    target_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class Commitment(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "commitments"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_commitments_title_nonempty"),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="ck_commitments_date_range",
        ),
        CheckConstraint(
            "estimated_duration_minutes IS NULL OR estimated_duration_minutes >= 0",
            name="ck_commitments_duration_nonnegative",
        ),
        CheckConstraint(
            "((planned_cost_minor IS NULL AND financial_buffer_requirement_minor IS NULL) "
            "AND currency_code IS NULL) OR ((planned_cost_minor IS NOT NULL "
            "OR financial_buffer_requirement_minor IS NOT NULL) "
            "AND (planned_cost_minor IS NULL OR planned_cost_minor >= 0) "
            "AND (financial_buffer_requirement_minor IS NULL "
            "OR financial_buffer_requirement_minor >= 0) "
            "AND length(currency_code) = 3 AND currency_code = upper(currency_code))",
            name="ck_commitments_money_shape",
        ),
        CheckConstraint("revision >= 1", name="ck_commitments_revision_positive"),
        Index("ix_commitments_workspace_status", "workspace_id", "status"),
        Index("ix_commitments_workspace_category", "workspace_id", "category"),
        Index("ix_commitments_workspace_target", "workspace_id", "ends_at"),
    )

    title: str = Field(max_length=255)
    description_markdown: str | None = Field(default=None, sa_type=Text)
    status: CommitmentStatus = Field(default=CommitmentStatus.DRAFT)
    category: str | None = Field(default=None, max_length=120)
    starts_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    ends_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    decision_deadline_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    planned_cost_minor: int | None = Field(default=None, ge=0)
    financial_buffer_requirement_minor: int | None = Field(default=None, ge=0)
    currency_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        sa_type=CurrencyCodeType,
    )


class CommitmentEntityLink(WorkspaceLinkBase, table=True):
    __tablename__ = "commitment_entity_links"
    __table_args__ = (
        UniqueConstraint(
            "commitment_id",
            "entity_type",
            "entity_id",
            name="uq_commitment_entity_link",
        ),
    )

    commitment_id: UUID = Field(
        foreign_key="commitments.id",
        ondelete="CASCADE",
        index=True,
    )
    entity_type: CommitmentEntityType
    entity_id: UUID = Field(index=True)
    role: str | None = Field(default=None, max_length=80)


class AutomationRule(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "automation_rules"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_rules_name_nonempty"),
        CheckConstraint("revision >= 1", name="ck_rules_revision_positive"),
        Index("ix_rules_workspace_enabled", "workspace_id", "enabled"),
    )

    name: str = Field(max_length=160)
    description: str | None = Field(default=None, sa_type=Text)
    enabled: bool = Field(default=True)
    trigger: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    action: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    last_run_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    next_run_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class Scenario(WorkspaceSoftDeleteEntityBase, table=True):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_scenarios_name_nonempty"),
        CheckConstraint("base_revision >= 1", name="ck_scenarios_base_revision_positive"),
        CheckConstraint("revision >= 1", name="ck_scenarios_revision_positive"),
        Index("ix_scenarios_workspace_status", "workspace_id", "status"),
    )

    name: str = Field(max_length=160)
    description_markdown: str | None = Field(default=None, sa_type=Text)
    status: ScenarioStatus = Field(default=ScenarioStatus.DRAFT)
    base_revision: int = Field(default=1, ge=1)


class ScenarioChange(WorkspaceEntityBase, table=True):
    __tablename__ = "scenario_changes"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_scenario_changes_revision_positive"),
        UniqueConstraint(
            "scenario_id",
            "entity_type",
            "entity_id",
            name="uq_scenario_entity_change",
        ),
        Index("ix_scenario_changes_scenario", "scenario_id", "created_at"),
    )

    scenario_id: UUID = Field(foreign_key="scenarios.id", ondelete="CASCADE", index=True)
    entity_type: DomainEntityType
    entity_id: UUID = Field(index=True)
    operation: ScenarioOperation
    changes: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
