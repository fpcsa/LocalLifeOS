from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.models import (
    CalendarEvent,
    CommitmentEntityLink,
    CommitmentEntityType,
    DomainEntityType,
    Goal,
    Note,
    PlannedTransaction,
    SavingsGoal,
    Task,
    TimelineEvent,
    Transaction,
)
from app.models.common import WorkspaceSoftDeleteEntityBase
from app.repositories.commitments import CommitmentRepository
from app.schemas.commitments import (
    AssessmentEntityReference,
    UnifiedTimelineEntityType,
    UnifiedTimelineItem,
)
from app.schemas.common import SortOrder
from app.services.workspace import get_current_workspace, get_preferences

LINK_TO_TIMELINE_TYPE = {
    CommitmentEntityType.TASK: UnifiedTimelineEntityType.TASK,
    CommitmentEntityType.CALENDAR_EVENT: UnifiedTimelineEntityType.CALENDAR_EVENT,
    CommitmentEntityType.NOTE: UnifiedTimelineEntityType.NOTE,
    CommitmentEntityType.PLANNED_TRANSACTION: UnifiedTimelineEntityType.PLANNED_TRANSACTION,
    CommitmentEntityType.TRANSACTION: UnifiedTimelineEntityType.TRANSACTION,
    CommitmentEntityType.SAVINGS_GOAL: UnifiedTimelineEntityType.SAVINGS_GOAL,
    CommitmentEntityType.GOAL: UnifiedTimelineEntityType.GOAL,
}


def _all_active[ModelT: WorkspaceSoftDeleteEntityBase](
    session: Session,
    model: type[ModelT],
    workspace_id: UUID,
) -> list[ModelT]:
    return list(
        session.exec(
            select(model).where(
                col(model.workspace_id) == workspace_id,
                col(model.deleted_at).is_(None),
            )
        ).all()
    )


def _all_commitment_relations(
    session: Session,
    workspace_id: UUID,
) -> dict[tuple[UnifiedTimelineEntityType, UUID], list[AssessmentEntityReference]]:
    relationships: dict[tuple[UnifiedTimelineEntityType, UUID], list[AssessmentEntityReference]] = (
        defaultdict(list)
    )
    links = session.exec(
        select(CommitmentEntityLink).where(col(CommitmentEntityLink.workspace_id) == workspace_id)
    ).all()
    for link in links:
        timeline_type = LINK_TO_TIMELINE_TYPE.get(link.entity_type)
        if timeline_type is not None:
            relationships[(timeline_type, link.entity_id)].append(
                AssessmentEntityReference(
                    entity_type="commitment",
                    entity_id=link.commitment_id,
                )
            )
    return relationships


def _item(
    entity_type: UnifiedTimelineEntityType,
    entity_id: UUID,
    occurred_at: datetime,
    kind: str,
    title: str,
    *,
    status: str | None = None,
    sensitive: bool = False,
    related: list[AssessmentEntityReference] | None = None,
    source_id: UUID | None = None,
) -> UnifiedTimelineItem:
    return UnifiedTimelineItem(
        item_id=f"{entity_type.value}:{source_id or entity_id}:{kind}",
        entity_type=entity_type,
        entity_id=entity_id,
        occurred_at=occurred_at,
        kind=kind,
        title=title,
        status=status,
        sensitive=sensitive,
        related_entities=related or [],
    )


def _allowed_for_commitment(
    session: Session,
    workspace_id: UUID,
    commitment_id: UUID,
) -> dict[UnifiedTimelineEntityType, set[UUID]]:
    repository = CommitmentRepository(session)
    if repository.get_active(workspace_id, commitment_id) is None:
        raise DomainNotFoundError("commitment", commitment_id)
    allowed: dict[UnifiedTimelineEntityType, set[UUID]] = defaultdict(set)
    allowed[UnifiedTimelineEntityType.COMMITMENT].add(commitment_id)
    for link in repository.links_for([commitment_id]).get(commitment_id, []):
        timeline_type = LINK_TO_TIMELINE_TYPE.get(link.entity_type)
        if timeline_type is not None:
            allowed[timeline_type].add(link.entity_id)
    return allowed


def list_unified_timeline(
    session: Session,
    *,
    page: int,
    page_size: int,
    start: datetime | None,
    end: datetime | None,
    entity_type: UnifiedTimelineEntityType | None,
    entity_id: UUID | None,
    order: SortOrder,
    commitment_id: UUID | None = None,
) -> tuple[list[UnifiedTimelineItem], int]:
    if start is not None and end is not None and end <= start:
        raise DomainValidationError("invalid_range", "end must be after start.")
    workspace = get_current_workspace(session)
    timezone_name = get_preferences(session).timezone
    timezone = ZoneInfo(timezone_name)
    relationships = _all_commitment_relations(session, workspace.id)
    allowed = (
        _allowed_for_commitment(session, workspace.id, commitment_id)
        if commitment_id is not None
        else None
    )
    items: list[UnifiedTimelineItem] = []

    for task in _all_active(session, Task, workspace.id):
        occurred = task.scheduled_start_at or task.due_at or task.updated_at
        kind = (
            "task_schedule"
            if task.scheduled_start_at is not None
            else "task_deadline"
            if task.due_at is not None
            else "task_activity"
        )
        items.append(
            _item(
                UnifiedTimelineEntityType.TASK,
                task.id,
                occurred,
                kind,
                task.title,
                status=task.status.value,
                related=relationships.get((UnifiedTimelineEntityType.TASK, task.id)),
            )
        )
    for event in _all_active(session, CalendarEvent, workspace.id):
        if event.all_day:
            if event.all_day_start is None:
                continue
            occurred = datetime.combine(event.all_day_start, time.min, timezone).astimezone(UTC)
        elif event.starts_at is not None:
            occurred = event.starts_at
        else:
            continue
        items.append(
            _item(
                UnifiedTimelineEntityType.CALENDAR_EVENT,
                event.id,
                occurred,
                "calendar_event",
                event.title,
                status=event.status.value,
                related=relationships.get((UnifiedTimelineEntityType.CALENDAR_EVENT, event.id)),
            )
        )
    for note in _all_active(session, Note, workspace.id):
        items.append(
            _item(
                UnifiedTimelineEntityType.NOTE,
                note.id,
                note.updated_at,
                "note_activity",
                note.title,
                related=relationships.get((UnifiedTimelineEntityType.NOTE, note.id)),
            )
        )
    for actual in _all_active(session, Transaction, workspace.id):
        items.append(
            _item(
                UnifiedTimelineEntityType.TRANSACTION,
                actual.id,
                actual.occurred_at,
                "posted_transaction",
                f"{actual.transaction_type.value.title()} transaction",
                status="posted",
                sensitive=True,
                related=relationships.get((UnifiedTimelineEntityType.TRANSACTION, actual.id)),
            )
        )
    for planned in _all_active(session, PlannedTransaction, workspace.id):
        items.append(
            _item(
                UnifiedTimelineEntityType.PLANNED_TRANSACTION,
                planned.id,
                planned.planned_for,
                "planned_transaction",
                f"Planned {planned.transaction_type.value}",
                status=planned.status.value,
                sensitive=True,
                related=relationships.get(
                    (UnifiedTimelineEntityType.PLANNED_TRANSACTION, planned.id)
                ),
            )
        )
    for savings_goal in _all_active(session, SavingsGoal, workspace.id):
        occurred = (
            datetime.combine(savings_goal.target_date, time.min, timezone).astimezone(UTC)
            if savings_goal.target_date is not None
            else savings_goal.updated_at
        )
        items.append(
            _item(
                UnifiedTimelineEntityType.SAVINGS_GOAL,
                savings_goal.id,
                occurred,
                "savings_goal_milestone",
                savings_goal.name,
                status=savings_goal.status.value,
                sensitive=True,
                related=relationships.get(
                    (UnifiedTimelineEntityType.SAVINGS_GOAL, savings_goal.id)
                ),
            )
        )
    for general_goal in _all_active(session, Goal, workspace.id):
        items.append(
            _item(
                UnifiedTimelineEntityType.GOAL,
                general_goal.id,
                general_goal.target_at or general_goal.updated_at,
                "goal_milestone" if general_goal.target_at is not None else "goal_progress",
                general_goal.title,
                status=general_goal.status.value,
                related=relationships.get((UnifiedTimelineEntityType.GOAL, general_goal.id)),
            )
        )
    commitment_events = session.exec(
        select(TimelineEvent).where(
            col(TimelineEvent.workspace_id) == workspace.id,
            col(TimelineEvent.entity_type) == DomainEntityType.COMMITMENT,
        )
    ).all()
    for timeline_event in commitment_events:
        items.append(
            _item(
                UnifiedTimelineEntityType.COMMITMENT,
                timeline_event.entity_id,
                timeline_event.occurred_at,
                timeline_event.action,
                timeline_event.title,
                related=[],
                source_id=timeline_event.id,
            )
        )

    if allowed is not None:
        items = [item for item in items if item.entity_id in allowed.get(item.entity_type, set())]
    if entity_type is not None:
        items = [item for item in items if item.entity_type == entity_type]
    if entity_id is not None:
        items = [item for item in items if item.entity_id == entity_id]
    if start is not None:
        items = [item for item in items if item.occurred_at >= start]
    if end is not None:
        items = [item for item in items if item.occurred_at < end]
    reverse = order == SortOrder.DESC
    items.sort(
        key=lambda item: (item.occurred_at, item.entity_type.value, item.item_id),
        reverse=reverse,
    )
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total
