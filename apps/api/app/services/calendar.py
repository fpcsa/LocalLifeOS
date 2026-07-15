from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import (
    AutomationTriggerType,
    CalendarEvent,
    CalendarEventEntityLink,
    CalendarEventStatus,
    CommitmentEntityType,
    DomainEntityType,
    NoteEntityLink,
)
from app.repositories.calendar import CalendarEventRepository
from app.schemas.common import DeletedResource
from app.schemas.productivity import (
    CalendarConflictOccurrence,
    CalendarConflictResponse,
    CalendarEventCreateRequest,
    CalendarEventResponse,
    CalendarEventUpdateRequest,
    CalendarMoveRequest,
    CalendarResizeRequest,
    DomainLinkResponse,
    RecurrenceOccurrenceResponse,
)
from app.services.automation import dispatch_automation_event
from app.services.domain_links import (
    remove_generic_links,
    replace_calendar_entity_links,
    replace_commitment_links,
)
from app.services.events import emit_timeline_event
from app.services.recurrence import recurrence_values
from app.services.workspace import get_current_workspace, get_preferences
from app.utils.recurrence import expand_recurrence

CALENDAR_LINK_TYPES = frozenset(
    {
        DomainEntityType.PROJECT,
        DomainEntityType.TASK,
        DomainEntityType.NOTE,
        DomainEntityType.GOAL,
    }
)
MAX_BUFFER = timedelta(days=7)


@dataclass(frozen=True)
class EventOccurrence:
    event: CalendarEvent
    starts_at: datetime
    ends_at: datetime
    all_day: bool

    @property
    def effective_starts_at(self) -> datetime:
        before = self.event.preparation_buffer_minutes + self.event.travel_buffer_minutes
        return self.starts_at - timedelta(minutes=before)

    @property
    def effective_ends_at(self) -> datetime:
        return self.ends_at + timedelta(minutes=self.event.recovery_buffer_minutes)


def _all_day_bounds(
    start_date: date,
    end_date: date,
    timezone_name: str,
) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(timezone_name)
    starts_at = datetime.combine(start_date, time.min, tzinfo=timezone).astimezone(UTC)
    ends_at = datetime.combine(end_date, time.min, tzinfo=timezone).astimezone(UTC)
    return starts_at, ends_at


def _event_occurrences(
    event: CalendarEvent,
    range_start: datetime,
    range_end: datetime,
    user_timezone: str,
    *,
    include_cancelled: bool = False,
) -> list[EventOccurrence]:
    if event.status == CalendarEventStatus.CANCELLED and not include_cancelled:
        return []
    if event.all_day:
        if event.all_day_start is None or event.all_day_end is None:
            return []
        timezone_name = event.timezone or user_timezone
        base_start, base_end = _all_day_bounds(
            event.all_day_start,
            event.all_day_end,
            timezone_name,
        )
    else:
        if event.starts_at is None or event.ends_at is None:
            return []
        base_start, base_end = event.starts_at, event.ends_at
    duration = base_end - base_start

    starts: list[datetime]
    if event.recurrence_rrule is None:
        starts = [base_start]
    else:
        try:
            starts = expand_recurrence(
                event.recurrence_rrule,
                dtstart=base_start,
                range_start=range_start - duration,
                range_end=range_end,
            )
        except ValueError as exc:
            raise DomainValidationError("invalid_recurrence", str(exc)) from exc
    return [
        EventOccurrence(
            event=event,
            starts_at=start,
            ends_at=start + duration,
            all_day=event.all_day,
        )
        for start in starts
        if start < range_end and start + duration > range_start
    ]


def _event_responses(
    repository: CalendarEventRepository,
    events: list[CalendarEvent],
) -> list[CalendarEventResponse]:
    event_ids = [event.id for event in events]
    entity_links = repository.entity_links_for(event_ids)
    commitment_ids = repository.commitment_ids_for(event_ids)
    attachment_ids = repository.attachment_ids_for(event_ids)
    responses: list[CalendarEventResponse] = []
    for event in events:
        values = event.model_dump(
            exclude={
                "deleted_at",
                "recurrence_frequency",
                "recurrence_interval",
                "recurrence_days_of_week",
                "recurrence_end_at",
            }
        )
        responses.append(
            CalendarEventResponse(
                **values,
                linked_entities=[
                    DomainLinkResponse(
                        id=link.id,
                        entity_type=link.entity_type,
                        entity_id=link.entity_id,
                        created_at=link.created_at,
                    )
                    for link in entity_links.get(event.id, [])
                ],
                commitment_ids=commitment_ids.get(event.id, []),
                attachment_ids=attachment_ids.get(event.id, []),
            )
        )
    return responses


def _candidate_events(
    session: Session,
    *,
    range_start: datetime,
    range_end: datetime,
    query: str | None,
    category: str | None,
    status: CalendarEventStatus | None,
    timezone_name: str,
) -> tuple[CalendarEventRepository, list[CalendarEvent]]:
    workspace = get_current_workspace(session)
    local_timezone = ZoneInfo(timezone_name)
    local_start_date = range_start.astimezone(local_timezone).date()
    local_end_date = range_end.astimezone(local_timezone).date() + timedelta(days=1)
    repository = CalendarEventRepository(session)
    candidates = repository.list_candidates(
        workspace.id,
        range_start=range_start,
        range_end=range_end,
        local_start_date=local_start_date,
        local_end_date=local_end_date,
        query=query,
        category=category,
        status=status,
    )
    return repository, candidates


def list_calendar_events(
    session: Session,
    *,
    range_start: datetime,
    range_end: datetime,
    page: int,
    page_size: int,
    query: str | None,
    category: str | None,
    status: CalendarEventStatus | None,
    timezone_name: str | None,
) -> tuple[list[CalendarEventResponse], int]:
    if range_end <= range_start:
        raise DomainValidationError("invalid_range", "end must be after start.")
    user_timezone = timezone_name or get_preferences(session).timezone
    repository, candidates = _candidate_events(
        session,
        range_start=range_start,
        range_end=range_end,
        query=query,
        category=category,
        status=status,
        timezone_name=user_timezone,
    )
    matching = [
        event
        for event in candidates
        if _event_occurrences(
            event,
            range_start,
            range_end,
            user_timezone,
            include_cancelled=True,
        )
    ]
    total = len(matching)
    start = (page - 1) * page_size
    return _event_responses(repository, matching[start : start + page_size]), total


def get_calendar_event(session: Session, event_id: UUID) -> CalendarEventResponse:
    workspace = get_current_workspace(session)
    repository = CalendarEventRepository(session)
    event = repository.get_active(workspace.id, event_id)
    if event is None:
        raise DomainNotFoundError("calendar_event", event_id)
    return _event_responses(repository, [event])[0]


def create_calendar_event(
    session: Session,
    create_data: CalendarEventCreateRequest,
) -> CalendarEventResponse:
    workspace = get_current_workspace(session)
    values = create_data.model_dump(exclude={"recurrence", "linked_entities", "commitment_ids"})
    values.update(recurrence_values(create_data.recurrence))
    repository = CalendarEventRepository(session)
    with transaction(session):
        event = repository.add(CalendarEvent(workspace_id=workspace.id, **values))
        replace_calendar_entity_links(
            session,
            workspace.id,
            event.id,
            create_data.linked_entities,
            CALENDAR_LINK_TYPES,
        )
        replace_commitment_links(
            session,
            workspace.id,
            CommitmentEntityType.CALENDAR_EVENT,
            event.id,
            create_data.commitment_ids,
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.CALENDAR_EVENT,
            entity_id=event.id,
            action="calendar_event_created",
            title=f"Calendar event created: {event.title}",
        )
    dispatch_automation_event(
        session,
        AutomationTriggerType.EVENT_CREATED,
        context={
            "entity_type": DomainEntityType.CALENDAR_EVENT.value,
            "entity_id": str(event.id),
            "title": event.title,
            "category": event.category,
            "location": event.location,
            "status": event.status.value,
            "timezone": event.timezone,
        },
        source_key=f"calendar-event:{event.id}",
    )
    return _event_responses(repository, [event])[0]


def update_calendar_event(
    session: Session,
    event_id: UUID,
    update_data: CalendarEventUpdateRequest,
) -> CalendarEventResponse:
    workspace = get_current_workspace(session)
    repository = CalendarEventRepository(session)
    if repository.get_active(workspace.id, event_id) is None:
        raise DomainNotFoundError("calendar_event", event_id)
    fields = update_data.model_fields_set
    values = update_data.model_dump(
        exclude={"revision", "recurrence", "linked_entities", "commitment_ids"},
        exclude_unset=True,
    )
    if "recurrence" in fields:
        values.update(recurrence_values(update_data.recurrence))
    if not values and "linked_entities" not in fields and "commitment_ids" not in fields:
        raise DomainValidationError("empty_update", "At least one calendar field is required.")
    with transaction(session):
        event = repository.update(workspace.id, event_id, update_data.revision, values)
        if update_data.linked_entities is not None:
            replace_calendar_entity_links(
                session,
                workspace.id,
                event.id,
                update_data.linked_entities,
                CALENDAR_LINK_TYPES,
            )
        if update_data.commitment_ids is not None:
            replace_commitment_links(
                session,
                workspace.id,
                CommitmentEntityType.CALENDAR_EVENT,
                event.id,
                update_data.commitment_ids,
            )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.CALENDAR_EVENT,
            entity_id=event.id,
            action="calendar_event_updated",
            title=f"Calendar event updated: {event.title}",
            payload={"fields": sorted(fields - {"revision"})},
        )
    return _event_responses(repository, [event])[0]


def move_calendar_event(
    session: Session,
    event_id: UUID,
    request: CalendarMoveRequest,
) -> CalendarEventResponse:
    workspace = get_current_workspace(session)
    repository = CalendarEventRepository(session)
    current = repository.get_active(workspace.id, event_id)
    if current is None:
        raise DomainNotFoundError("calendar_event", event_id)
    values: dict[str, object]
    if current.all_day:
        if request.all_day_start is None or request.starts_at is not None:
            raise DomainValidationError(
                "invalid_event_move",
                "All-day events must be moved with all_day_start.",
            )
        if current.all_day_start is None or current.all_day_end is None:
            raise DomainValidationError("invalid_event", "All-day event dates are incomplete.")
        duration = current.all_day_end - current.all_day_start
        values = {
            "all_day_start": request.all_day_start,
            "all_day_end": request.all_day_start + duration,
        }
    else:
        if request.starts_at is None or request.all_day_start is not None:
            raise DomainValidationError(
                "invalid_event_move",
                "Timed events must be moved with starts_at.",
            )
        if current.starts_at is None or current.ends_at is None:
            raise DomainValidationError("invalid_event", "Timed event dates are incomplete.")
        values = {
            "starts_at": request.starts_at,
            "ends_at": request.starts_at + (current.ends_at - current.starts_at),
        }
    if request.timezone is not None:
        values["timezone"] = request.timezone
    with transaction(session):
        event = repository.update(workspace.id, event_id, request.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.CALENDAR_EVENT,
            entity_id=event.id,
            action="calendar_event_moved",
            title=f"Calendar event moved: {event.title}",
        )
    return _event_responses(repository, [event])[0]


def resize_calendar_event(
    session: Session,
    event_id: UUID,
    request: CalendarResizeRequest,
) -> CalendarEventResponse:
    workspace = get_current_workspace(session)
    repository = CalendarEventRepository(session)
    current = repository.get_active(workspace.id, event_id)
    if current is None:
        raise DomainNotFoundError("calendar_event", event_id)
    if current.all_day:
        if request.all_day_end is None or current.all_day_start is None:
            raise DomainValidationError(
                "invalid_event_resize",
                "All-day events must be resized with all_day_end.",
            )
        if request.all_day_end <= current.all_day_start:
            raise DomainValidationError("invalid_event_resize", "End must be after start.")
        values: dict[str, object] = {"all_day_end": request.all_day_end}
    else:
        if request.ends_at is None or current.starts_at is None:
            raise DomainValidationError(
                "invalid_event_resize",
                "Timed events must be resized with ends_at.",
            )
        if request.ends_at <= current.starts_at:
            raise DomainValidationError("invalid_event_resize", "End must be after start.")
        values = {"ends_at": request.ends_at}
    with transaction(session):
        event = repository.update(workspace.id, event_id, request.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.CALENDAR_EVENT,
            entity_id=event.id,
            action="calendar_event_resized",
            title=f"Calendar event resized: {event.title}",
        )
    return _event_responses(repository, [event])[0]


def delete_calendar_event(
    session: Session,
    event_id: UUID,
    revision: int,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = CalendarEventRepository(session)
    current = repository.get_active(workspace.id, event_id)
    if current is None:
        raise DomainNotFoundError("calendar_event", event_id)
    with transaction(session):
        own_links = session.exec(
            select(CalendarEventEntityLink).where(
                col(CalendarEventEntityLink.calendar_event_id) == event_id
            )
        ).all()
        for event_link in own_links:
            session.delete(event_link)
        note_links = session.exec(
            select(NoteEntityLink).where(
                col(NoteEntityLink.entity_type) == DomainEntityType.CALENDAR_EVENT,
                col(NoteEntityLink.entity_id) == event_id,
            )
        ).all()
        for note_link in note_links:
            session.delete(note_link)
        remove_generic_links(
            session,
            workspace.id,
            DomainEntityType.CALENDAR_EVENT,
            CommitmentEntityType.CALENDAR_EVENT,
            event_id,
        )
        event = repository.soft_delete(workspace.id, event_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.CALENDAR_EVENT,
            entity_id=event.id,
            action="calendar_event_deleted",
            title=f"Calendar event deleted: {event.title}",
        )
    return DeletedResource(id=event_id)


def expand_calendar_occurrences(
    session: Session,
    event_id: UUID,
    range_start: datetime,
    range_end: datetime,
) -> list[RecurrenceOccurrenceResponse]:
    workspace = get_current_workspace(session)
    event = CalendarEventRepository(session).get_active(workspace.id, event_id)
    if event is None:
        raise DomainNotFoundError("calendar_event", event_id)
    occurrences = _event_occurrences(
        event,
        range_start,
        range_end,
        get_preferences(session).timezone,
        include_cancelled=True,
    )
    return [
        RecurrenceOccurrenceResponse(starts_at=item.starts_at, ends_at=item.ends_at)
        for item in occurrences
    ]


def calendar_occurrences_in_range(
    session: Session,
    *,
    range_start: datetime,
    range_end: datetime,
) -> list[EventOccurrence]:
    """Return active occurrences whose buffer-expanded interval touches the range."""

    if range_end <= range_start:
        raise DomainValidationError("invalid_range", "end must be after start.")
    user_timezone = get_preferences(session).timezone
    _, candidates = _candidate_events(
        session,
        range_start=range_start - MAX_BUFFER,
        range_end=range_end + MAX_BUFFER,
        query=None,
        category=None,
        status=None,
        timezone_name=user_timezone,
    )
    occurrences = [
        occurrence
        for event in candidates
        for occurrence in _event_occurrences(
            event,
            range_start - MAX_BUFFER,
            range_end + MAX_BUFFER,
            user_timezone,
        )
        if occurrence.effective_starts_at < range_end and occurrence.effective_ends_at > range_start
    ]
    occurrences.sort(
        key=lambda item: (
            item.effective_starts_at,
            item.effective_ends_at,
            str(item.event.id),
        )
    )
    return occurrences


def detect_calendar_conflicts(
    session: Session,
    *,
    range_start: datetime,
    range_end: datetime,
    timezone_name: str | None,
) -> list[CalendarConflictResponse]:
    if range_end <= range_start:
        raise DomainValidationError("invalid_range", "end must be after start.")
    user_timezone = timezone_name or get_preferences(session).timezone
    _, candidates = _candidate_events(
        session,
        range_start=range_start - MAX_BUFFER,
        range_end=range_end + MAX_BUFFER,
        query=None,
        category=None,
        status=None,
        timezone_name=user_timezone,
    )
    occurrences = [
        occurrence
        for event in candidates
        for occurrence in _event_occurrences(
            event,
            range_start - MAX_BUFFER,
            range_end + MAX_BUFFER,
            user_timezone,
        )
        if occurrence.effective_starts_at < range_end and occurrence.effective_ends_at > range_start
    ]
    occurrences.sort(key=lambda item: (item.effective_starts_at, str(item.event.id)))
    conflicts: list[CalendarConflictResponse] = []
    for index, first in enumerate(occurrences):
        for second in occurrences[index + 1 :]:
            if second.effective_starts_at >= first.effective_ends_at:
                break
            if first.event.id == second.event.id:
                continue
            if first.effective_starts_at < second.effective_ends_at:
                conflicts.append(
                    CalendarConflictResponse(
                        first=_conflict_occurrence(first),
                        second=_conflict_occurrence(second),
                    )
                )
    return conflicts


def _conflict_occurrence(occurrence: EventOccurrence) -> CalendarConflictOccurrence:
    return CalendarConflictOccurrence(
        event_id=occurrence.event.id,
        title=occurrence.event.title,
        starts_at=occurrence.starts_at,
        ends_at=occurrence.ends_at,
        effective_starts_at=occurrence.effective_starts_at,
        effective_ends_at=occurrence.effective_ends_at,
        all_day=occurrence.all_day,
    )
