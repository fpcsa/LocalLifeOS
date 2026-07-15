from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import CalendarEventStatus
from app.schemas.common import (
    AwareDateTime,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
    TimezoneName,
)
from app.schemas.productivity import (
    CalendarConflictResponse,
    CalendarEventCreateRequest,
    CalendarEventResponse,
    CalendarEventUpdateRequest,
    CalendarMoveRequest,
    CalendarResizeRequest,
    RecurrenceOccurrenceResponse,
)
from app.services.calendar import (
    create_calendar_event,
    delete_calendar_event,
    detect_calendar_conflicts,
    expand_calendar_occurrences,
    get_calendar_event,
    list_calendar_events,
    move_calendar_event,
    resize_calendar_event,
    update_calendar_event,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/conflicts", response_model=DataEnvelope[list[CalendarConflictResponse]])
def read_calendar_conflicts(
    session: SessionDependency,
    start: AwareDateTime,
    end: AwareDateTime,
    timezone_name: Annotated[TimezoneName | None, Query(alias="timezone")] = None,
) -> DataEnvelope[list[CalendarConflictResponse]]:
    return DataEnvelope(
        data=detect_calendar_conflicts(
            session,
            range_start=start,
            range_end=end,
            timezone_name=timezone_name,
        )
    )


@router.get("/events", response_model=ListEnvelope[CalendarEventResponse])
def read_calendar_events(
    session: SessionDependency,
    start: AwareDateTime,
    end: AwareDateTime,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=255)] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    event_status: Annotated[CalendarEventStatus | None, Query(alias="status")] = None,
    timezone_name: Annotated[TimezoneName | None, Query(alias="timezone")] = None,
) -> ListEnvelope[CalendarEventResponse]:
    items, total = list_calendar_events(
        session,
        range_start=start,
        range_end=end,
        page=page,
        page_size=page_size,
        query=query,
        category=category,
        status=event_status,
        timezone_name=timezone_name,
    )
    return ListEnvelope(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.post(
    "/events",
    response_model=DataEnvelope[CalendarEventResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_calendar_event(
    create_data: CalendarEventCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[CalendarEventResponse]:
    return DataEnvelope(data=create_calendar_event(session, create_data))


@router.get("/events/{event_id}", response_model=DataEnvelope[CalendarEventResponse])
def read_calendar_event(
    event_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[CalendarEventResponse]:
    return DataEnvelope(data=get_calendar_event(session, event_id))


@router.patch("/events/{event_id}", response_model=DataEnvelope[CalendarEventResponse])
def patch_calendar_event(
    event_id: UUID,
    update_data: CalendarEventUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[CalendarEventResponse]:
    return DataEnvelope(data=update_calendar_event(session, event_id, update_data))


@router.delete("/events/{event_id}", response_model=DataEnvelope[DeletedResource])
def remove_calendar_event(
    event_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_calendar_event(session, event_id, revision))


@router.post("/events/{event_id}/move", response_model=DataEnvelope[CalendarEventResponse])
def post_calendar_move(
    event_id: UUID,
    request: CalendarMoveRequest,
    session: SessionDependency,
) -> DataEnvelope[CalendarEventResponse]:
    return DataEnvelope(data=move_calendar_event(session, event_id, request))


@router.post("/events/{event_id}/resize", response_model=DataEnvelope[CalendarEventResponse])
def post_calendar_resize(
    event_id: UUID,
    request: CalendarResizeRequest,
    session: SessionDependency,
) -> DataEnvelope[CalendarEventResponse]:
    return DataEnvelope(data=resize_calendar_event(session, event_id, request))


@router.get(
    "/events/{event_id}/occurrences",
    response_model=DataEnvelope[list[RecurrenceOccurrenceResponse]],
)
def read_calendar_occurrences(
    event_id: UUID,
    session: SessionDependency,
    start: AwareDateTime,
    end: AwareDateTime,
) -> DataEnvelope[list[RecurrenceOccurrenceResponse]]:
    return DataEnvelope(data=expand_calendar_occurrences(session, event_id, start, end))
