from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.models import DomainEntityType, TimelineEvent
from app.repositories import TimelineRepository


def emit_timeline_event(
    session: Session,
    *,
    workspace_id: UUID,
    entity_type: DomainEntityType,
    entity_id: UUID,
    action: str,
    title: str,
    payload: dict[str, Any] | None = None,
) -> TimelineEvent:
    return TimelineRepository(session).add(
        TimelineEvent(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            title=title,
            payload=payload or {},
        )
    )
