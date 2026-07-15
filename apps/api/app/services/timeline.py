from __future__ import annotations

from sqlmodel import Session

from app.models import DomainEntityType, TimelineEvent
from app.repositories import PageResult, TimelineRepository
from app.schemas.common import SortOrder
from app.services.workspace import get_current_workspace


def list_timeline(
    session: Session,
    *,
    page: int,
    page_size: int,
    entity_type: DomainEntityType | None,
    action: str | None,
    order: SortOrder,
) -> PageResult[TimelineEvent]:
    workspace = get_current_workspace(session)
    return TimelineRepository(session).list(
        workspace.id,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        action=action,
        descending=order == SortOrder.DESC,
    )
