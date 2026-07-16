from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement
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


def _query_source[ModelT: WorkspaceSoftDeleteEntityBase, OccurredT](
    session: Session,
    model: type[ModelT],
    conditions: list[ColumnElement[bool]],
    occurred: ColumnElement[OccurredT],
    order: SortOrder,
    limit: int,
) -> tuple[list[ModelT], int]:
    count = session.exec(select(func.count()).select_from(model).where(*conditions)).one()
    ordering = occurred.desc() if order == SortOrder.DESC else occurred.asc()
    rows = session.exec(
        select(model).where(*conditions).order_by(ordering, col(model.id)).limit(limit)
    ).all()
    return list(rows), count


def _source_conditions[ModelT: WorkspaceSoftDeleteEntityBase](
    model: type[ModelT],
    workspace_id: UUID,
    timeline_type: UnifiedTimelineEntityType,
    allowed: dict[UnifiedTimelineEntityType, set[UUID]] | None,
    entity_id: UUID | None,
) -> list[ColumnElement[bool]] | None:
    conditions = [
        col(model.workspace_id) == workspace_id,
        col(model.deleted_at).is_(None),
    ]
    if allowed is not None:
        identifiers = allowed.get(timeline_type, set())
        if not identifiers:
            return None
        conditions.append(col(model.id).in_(identifiers))
    if entity_id is not None:
        conditions.append(col(model.id) == entity_id)
    return conditions


def _range_conditions(
    occurred: ColumnElement[datetime],
    start: datetime | None,
    end: datetime | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if start is not None:
        conditions.append(occurred >= start)
    if end is not None:
        conditions.append(occurred < end)
    return conditions


def _local_date_range_conditions(
    occurred: ColumnElement[date],
    start: datetime | None,
    end: datetime | None,
    timezone: ZoneInfo,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if start is not None:
        local_start = start.astimezone(timezone)
        minimum = local_start.date()
        if local_start.timetz().replace(tzinfo=None) > time.min:
            minimum += timedelta(days=1)
        conditions.append(occurred >= minimum)
    if end is not None:
        local_end = end.astimezone(timezone)
        maximum_exclusive = local_end.date()
        if local_end.timetz().replace(tzinfo=None) > time.min:
            maximum_exclusive += timedelta(days=1)
        conditions.append(occurred < maximum_exclusive)
    return conditions


def _page_relationships(
    session: Session,
    workspace_id: UUID,
    items: list[UnifiedTimelineItem],
) -> dict[tuple[UnifiedTimelineEntityType, UUID], list[AssessmentEntityReference]]:
    entity_ids = {item.entity_id for item in items}
    if not entity_ids:
        return {}
    relationships: dict[tuple[UnifiedTimelineEntityType, UUID], list[AssessmentEntityReference]] = (
        defaultdict(list)
    )
    links = session.exec(
        select(CommitmentEntityLink).where(
            col(CommitmentEntityLink.workspace_id) == workspace_id,
            col(CommitmentEntityLink.entity_id).in_(entity_ids),
        )
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
    allowed = (
        _allowed_for_commitment(session, workspace.id, commitment_id)
        if commitment_id is not None
        else None
    )
    items: list[UnifiedTimelineItem] = []
    total = 0
    source_limit = page * page_size

    def requested(timeline_type: UnifiedTimelineEntityType) -> bool:
        return entity_type is None or entity_type == timeline_type

    if requested(UnifiedTimelineEntityType.TASK):
        task_conditions = _source_conditions(
            Task, workspace.id, UnifiedTimelineEntityType.TASK, allowed, entity_id
        )
        if task_conditions is not None:
            occurred = cast(
                ColumnElement[datetime],
                func.coalesce(Task.scheduled_start_at, Task.due_at, Task.updated_at),
            )
            task_conditions.extend(_range_conditions(occurred, start, end))
            task_rows, count = _query_source(
                session, Task, task_conditions, occurred, order, source_limit
            )
            total += count
            for task in task_rows:
                task_occurred = task.scheduled_start_at or task.due_at or task.updated_at
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
                        task_occurred,
                        kind,
                        task.title,
                        status=task.status.value,
                    )
                )

    if requested(UnifiedTimelineEntityType.CALENDAR_EVENT):
        timed_conditions = _source_conditions(
            CalendarEvent,
            workspace.id,
            UnifiedTimelineEntityType.CALENDAR_EVENT,
            allowed,
            entity_id,
        )
        if timed_conditions is not None:
            timed_conditions.extend(
                [
                    col(CalendarEvent.all_day).is_(False),
                    col(CalendarEvent.starts_at).is_not(None),
                ]
            )
            timed_at = cast(ColumnElement[datetime], col(CalendarEvent.starts_at))
            timed_conditions.extend(_range_conditions(timed_at, start, end))
            timed_rows, count = _query_source(
                session,
                CalendarEvent,
                timed_conditions,
                timed_at,
                order,
                source_limit,
            )
            total += count
            for event in timed_rows:
                assert event.starts_at is not None
                items.append(
                    _item(
                        UnifiedTimelineEntityType.CALENDAR_EVENT,
                        event.id,
                        event.starts_at,
                        "calendar_event",
                        event.title,
                        status=event.status.value,
                    )
                )
        all_day_conditions = _source_conditions(
            CalendarEvent,
            workspace.id,
            UnifiedTimelineEntityType.CALENDAR_EVENT,
            allowed,
            entity_id,
        )
        if all_day_conditions is not None:
            all_day_conditions.extend(
                [
                    col(CalendarEvent.all_day).is_(True),
                    col(CalendarEvent.all_day_start).is_not(None),
                ]
            )
            all_day_at = cast(ColumnElement[date], col(CalendarEvent.all_day_start))
            all_day_conditions.extend(
                _local_date_range_conditions(all_day_at, start, end, timezone)
            )
            all_day_rows, count = _query_source(
                session,
                CalendarEvent,
                all_day_conditions,
                all_day_at,
                order,
                source_limit,
            )
            total += count
            for event in all_day_rows:
                assert event.all_day_start is not None
                all_day_occurred = datetime.combine(
                    event.all_day_start, time.min, timezone
                ).astimezone(UTC)
                items.append(
                    _item(
                        UnifiedTimelineEntityType.CALENDAR_EVENT,
                        event.id,
                        all_day_occurred,
                        "calendar_event",
                        event.title,
                        status=event.status.value,
                    )
                )

    simple_sources = (
        (
            UnifiedTimelineEntityType.NOTE,
            Note,
            cast(ColumnElement[datetime], col(Note.updated_at)),
        ),
        (
            UnifiedTimelineEntityType.TRANSACTION,
            Transaction,
            cast(ColumnElement[datetime], col(Transaction.occurred_at)),
        ),
        (
            UnifiedTimelineEntityType.PLANNED_TRANSACTION,
            PlannedTransaction,
            cast(ColumnElement[datetime], col(PlannedTransaction.planned_for)),
        ),
        (
            UnifiedTimelineEntityType.GOAL,
            Goal,
            cast(
                ColumnElement[datetime],
                func.coalesce(Goal.target_at, Goal.updated_at),
            ),
        ),
    )
    for timeline_type, model, occurred in simple_sources:
        if not requested(timeline_type):
            continue
        source_conditions = _source_conditions(
            model, workspace.id, timeline_type, allowed, entity_id
        )
        if source_conditions is None:
            continue
        source_conditions.extend(_range_conditions(occurred, start, end))
        source_rows, count = _query_source(
            session, model, source_conditions, occurred, order, source_limit
        )
        total += count
        for record in source_rows:
            if isinstance(record, Note):
                items.append(
                    _item(
                        timeline_type,
                        record.id,
                        record.updated_at,
                        "note_activity",
                        record.title,
                    )
                )
            elif isinstance(record, Transaction):
                items.append(
                    _item(
                        timeline_type,
                        record.id,
                        record.occurred_at,
                        "posted_transaction",
                        f"{record.transaction_type.value.title()} transaction",
                        status="posted",
                        sensitive=True,
                    )
                )
            elif isinstance(record, PlannedTransaction):
                items.append(
                    _item(
                        timeline_type,
                        record.id,
                        record.planned_for,
                        "planned_transaction",
                        f"Planned {record.transaction_type.value}",
                        status=record.status.value,
                        sensitive=True,
                    )
                )
            else:
                assert isinstance(record, Goal)
                goal_occurred = record.target_at or record.updated_at
                items.append(
                    _item(
                        timeline_type,
                        record.id,
                        goal_occurred,
                        "goal_milestone" if record.target_at else "goal_progress",
                        record.title,
                        status=record.status.value,
                    )
                )

    if requested(UnifiedTimelineEntityType.SAVINGS_GOAL):
        for with_target in (True, False):
            savings_conditions = _source_conditions(
                SavingsGoal,
                workspace.id,
                UnifiedTimelineEntityType.SAVINGS_GOAL,
                allowed,
                entity_id,
            )
            if savings_conditions is None:
                continue
            if with_target:
                savings_conditions.append(col(SavingsGoal.target_date).is_not(None))
                savings_at = cast(ColumnElement[date], col(SavingsGoal.target_date))
                savings_conditions.extend(
                    _local_date_range_conditions(savings_at, start, end, timezone)
                )
                savings_rows, count = _query_source(
                    session,
                    SavingsGoal,
                    savings_conditions,
                    savings_at,
                    order,
                    source_limit,
                )
            else:
                savings_conditions.append(col(SavingsGoal.target_date).is_(None))
                updated_at = cast(ColumnElement[datetime], col(SavingsGoal.updated_at))
                savings_conditions.extend(_range_conditions(updated_at, start, end))
                savings_rows, count = _query_source(
                    session,
                    SavingsGoal,
                    savings_conditions,
                    updated_at,
                    order,
                    source_limit,
                )
            total += count
            for savings_goal in savings_rows:
                savings_occurred = (
                    datetime.combine(savings_goal.target_date, time.min, timezone).astimezone(UTC)
                    if savings_goal.target_date is not None
                    else savings_goal.updated_at
                )
                items.append(
                    _item(
                        UnifiedTimelineEntityType.SAVINGS_GOAL,
                        savings_goal.id,
                        savings_occurred,
                        "savings_goal_milestone",
                        savings_goal.name,
                        status=savings_goal.status.value,
                        sensitive=True,
                    )
                )

    if requested(UnifiedTimelineEntityType.COMMITMENT):
        commitment_conditions: list[ColumnElement[bool]] = [
            col(TimelineEvent.workspace_id) == workspace.id,
            col(TimelineEvent.entity_type) == DomainEntityType.COMMITMENT,
        ]
        if allowed is not None:
            identifiers = allowed.get(UnifiedTimelineEntityType.COMMITMENT, set())
            if identifiers:
                commitment_conditions.append(col(TimelineEvent.entity_id).in_(identifiers))
            else:
                commitment_conditions.append(col(TimelineEvent.entity_id).in_(set()))
        if entity_id is not None:
            commitment_conditions.append(col(TimelineEvent.entity_id) == entity_id)
        commitment_at = cast(ColumnElement[datetime], col(TimelineEvent.occurred_at))
        commitment_conditions.extend(_range_conditions(commitment_at, start, end))
        count = session.exec(
            select(func.count()).select_from(TimelineEvent).where(*commitment_conditions)
        ).one()
        ordering = commitment_at.desc() if order == SortOrder.DESC else commitment_at.asc()
        commitment_events = session.exec(
            select(TimelineEvent)
            .where(*commitment_conditions)
            .order_by(ordering, col(TimelineEvent.id))
            .limit(source_limit)
        ).all()
        total += count
        for timeline_event in commitment_events:
            items.append(
                _item(
                    UnifiedTimelineEntityType.COMMITMENT,
                    timeline_event.entity_id,
                    timeline_event.occurred_at,
                    timeline_event.action,
                    timeline_event.title,
                    source_id=timeline_event.id,
                )
            )

    reverse = order == SortOrder.DESC
    items.sort(
        key=lambda item: (item.occurred_at, item.entity_type.value, item.item_id),
        reverse=reverse,
    )
    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size]
    relationships = _page_relationships(session, workspace.id, page_items)
    return [
        item.model_copy(
            update={"related_entities": relationships.get((item.entity_type, item.entity_id), [])}
        )
        for item in page_items
    ], total
