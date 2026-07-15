from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError
from app.models import (
    Budget,
    CalendarEvent,
    Commitment,
    CommitmentEntityLink,
    CommitmentEntityType,
    FinancialAccount,
    Goal,
    Note,
    PlannedTransaction,
    Project,
    SavingsGoal,
    Task,
    TaskDependency,
    Transaction,
)
from app.models.common import WorkspaceSoftDeleteEntityBase
from app.repositories.commitments import CommitmentRepository
from app.repositories.finance_engine import FinanceAccountRepository, FinanceTransactionRepository
from app.schemas.finance import BudgetConsumptionResponse
from app.schemas.productivity import CalendarConflictResponse
from app.services.calendar import detect_calendar_conflicts
from app.services.finance_reports import budget_consumption_report
from app.services.workspace import get_current_workspace, get_preferences


@dataclass
class CommitmentEvidence:
    commitment: Commitment
    timezone_name: str
    links: list[CommitmentEntityLink] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    events: list[CalendarEvent] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    planned_transactions: list[PlannedTransaction] = field(default_factory=list)
    actual_transactions: list[Transaction] = field(default_factory=list)
    budgets: list[Budget] = field(default_factory=list)
    savings_goals: list[SavingsGoal] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    dependencies: list[TaskDependency] = field(default_factory=list)
    dependency_targets: dict[UUID, Task | None] = field(default_factory=dict)
    calendar_conflicts: list[CalendarConflictResponse] = field(default_factory=list)
    budget_reports: dict[UUID, BudgetConsumptionResponse] = field(default_factory=dict)
    accounts: list[FinancialAccount] = field(default_factory=list)
    ledger_transactions: list[Transaction] = field(default_factory=list)
    missing_links: list[tuple[CommitmentEntityType, UUID]] = field(default_factory=list)


def _active_target[ModelT: WorkspaceSoftDeleteEntityBase](
    session: Session,
    model: type[ModelT],
    entity_id: UUID,
    workspace_id: UUID,
) -> ModelT | None:
    target = session.get(model, entity_id)
    if target is None or target.workspace_id != workspace_id or target.deleted_at is not None:
        return None
    return target


def _event_bounds(event: CalendarEvent) -> tuple[datetime, datetime] | None:
    if event.all_day:
        if event.all_day_start is None or event.all_day_end is None:
            return None
        timezone = ZoneInfo(event.timezone)
        starts_at = datetime.combine(event.all_day_start, time.min, timezone).astimezone(UTC)
        ends_at = datetime.combine(event.all_day_end, time.min, timezone).astimezone(UTC)
        return starts_at, ends_at
    if event.starts_at is None or event.ends_at is None:
        return None
    return event.starts_at, event.ends_at


def _collect_conflicts(session: Session, evidence: CommitmentEvidence) -> None:
    bounds = [bound for event in evidence.events if (bound := _event_bounds(event)) is not None]
    if evidence.commitment.starts_at is not None and evidence.commitment.ends_at is not None:
        bounds.append((evidence.commitment.starts_at, evidence.commitment.ends_at))
    if not bounds or not evidence.events:
        return
    range_start = min(bound[0] for bound in bounds) - timedelta(days=1)
    range_end = max(bound[1] for bound in bounds) + timedelta(days=1)
    linked_ids = {event.id for event in evidence.events}
    evidence.calendar_conflicts = [
        conflict
        for conflict in detect_calendar_conflicts(
            session,
            range_start=range_start,
            range_end=range_end,
            timezone_name=None,
        )
        if conflict.first.event_id in linked_ids or conflict.second.event_id in linked_ids
    ]


def collect_commitment_evidence(
    session: Session,
    commitment_id: UUID,
) -> CommitmentEvidence:
    workspace = get_current_workspace(session)
    repository = CommitmentRepository(session)
    commitment = repository.get_active(workspace.id, commitment_id)
    if commitment is None:
        raise DomainNotFoundError("commitment", commitment_id)
    links = repository.links_for([commitment_id]).get(commitment_id, [])
    evidence = CommitmentEvidence(
        commitment=commitment,
        timezone_name=get_preferences(session).timezone,
        links=links,
    )

    actual_by_id: dict[UUID, Transaction] = {}
    for link in links:
        target: object | None
        if link.entity_type == CommitmentEntityType.PROJECT:
            target = _active_target(session, Project, link.entity_id, workspace.id)
            if isinstance(target, Project):
                evidence.projects.append(target)
        elif link.entity_type == CommitmentEntityType.TASK:
            target = _active_target(session, Task, link.entity_id, workspace.id)
            if isinstance(target, Task):
                evidence.tasks.append(target)
        elif link.entity_type == CommitmentEntityType.CALENDAR_EVENT:
            target = _active_target(session, CalendarEvent, link.entity_id, workspace.id)
            if isinstance(target, CalendarEvent):
                evidence.events.append(target)
        elif link.entity_type == CommitmentEntityType.NOTE:
            target = _active_target(session, Note, link.entity_id, workspace.id)
            if isinstance(target, Note):
                evidence.notes.append(target)
        elif link.entity_type == CommitmentEntityType.PLANNED_TRANSACTION:
            target = _active_target(session, PlannedTransaction, link.entity_id, workspace.id)
            if isinstance(target, PlannedTransaction):
                evidence.planned_transactions.append(target)
                if target.actual_transaction_id is not None:
                    actual = _active_target(
                        session,
                        Transaction,
                        target.actual_transaction_id,
                        workspace.id,
                    )
                    if isinstance(actual, Transaction):
                        actual_by_id[actual.id] = actual
        elif link.entity_type == CommitmentEntityType.TRANSACTION:
            target = _active_target(session, Transaction, link.entity_id, workspace.id)
            if isinstance(target, Transaction):
                actual_by_id[target.id] = target
        elif link.entity_type == CommitmentEntityType.BUDGET:
            target = _active_target(session, Budget, link.entity_id, workspace.id)
            if isinstance(target, Budget):
                evidence.budgets.append(target)
        elif link.entity_type == CommitmentEntityType.SAVINGS_GOAL:
            target = _active_target(session, SavingsGoal, link.entity_id, workspace.id)
            if isinstance(target, SavingsGoal):
                evidence.savings_goals.append(target)
        else:
            target = _active_target(session, Goal, link.entity_id, workspace.id)
            if isinstance(target, Goal):
                evidence.goals.append(target)
        if target is None:
            evidence.missing_links.append((link.entity_type, link.entity_id))
    evidence.actual_transactions = list(actual_by_id.values())

    task_ids = [task.id for task in evidence.tasks]
    if task_ids:
        evidence.dependencies = list(
            session.exec(
                select(TaskDependency).where(
                    col(TaskDependency.workspace_id) == workspace.id,
                    col(TaskDependency.task_id).in_(task_ids),
                )
            ).all()
        )
        for dependency in evidence.dependencies:
            target = _active_target(
                session,
                Task,
                dependency.depends_on_task_id,
                workspace.id,
            )
            evidence.dependency_targets[dependency.id] = target

    for budget in evidence.budgets:
        evidence.budget_reports[budget.id] = budget_consumption_report(session, budget.id)

    evidence.accounts = FinanceAccountRepository(session).all_active(workspace.id)
    evidence.ledger_transactions = FinanceTransactionRepository(session).range(workspace.id)
    _collect_conflicts(session, evidence)
    return evidence
