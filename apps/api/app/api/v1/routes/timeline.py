from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import SessionDependency
from app.models import DomainEntityType
from app.schemas.commitments import UnifiedTimelineEntityType, UnifiedTimelineItem
from app.schemas.common import AwareDateTime, ListEnvelope, PaginationMeta, SortOrder
from app.schemas.resources import TimelineEventResponse
from app.services.timeline import list_timeline
from app.services.unified_timeline import list_unified_timeline

router = APIRouter(tags=["timeline"])


@router.get("/timeline", response_model=ListEnvelope[TimelineEventResponse])
def read_timeline(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    entity_type: DomainEntityType | None = None,
    action: Annotated[str | None, Query(max_length=50)] = None,
    order: SortOrder = SortOrder.DESC,
) -> ListEnvelope[TimelineEventResponse]:
    result = list_timeline(
        session,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        action=action,
        order=order,
    )
    return ListEnvelope(
        data=[TimelineEventResponse.model_validate(event) for event in result.items],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=result.total,
            total_pages=(result.total + page_size - 1) // page_size,
        ),
    )


@router.get("/timeline/unified", response_model=ListEnvelope[UnifiedTimelineItem])
def read_unified_timeline(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    start: AwareDateTime | None = None,
    end: AwareDateTime | None = None,
    entity_type: UnifiedTimelineEntityType | None = None,
    entity_id: UUID | None = None,
    commitment_id: UUID | None = None,
    order: SortOrder = SortOrder.DESC,
) -> ListEnvelope[UnifiedTimelineItem]:
    items, total = list_unified_timeline(
        session,
        page=page,
        page_size=page_size,
        start=start,
        end=end,
        entity_type=entity_type,
        entity_id=entity_id,
        commitment_id=commitment_id,
        order=order,
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
