from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import asc, desc, func
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models import DomainEntityType, TimelineEvent
from app.repositories.base import PageResult


class TimelineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: TimelineEvent) -> TimelineEvent:
        self.session.add(event)
        self.session.flush()
        self.session.refresh(event)
        return event

    def list(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        entity_type: DomainEntityType | None,
        action: str | None,
        descending: bool,
    ) -> PageResult[TimelineEvent]:
        filters: list[ColumnElement[bool]] = [col(TimelineEvent.workspace_id) == workspace_id]
        if entity_type is not None:
            filters.append(col(TimelineEvent.entity_type) == entity_type)
        if action:
            filters.append(col(TimelineEvent.action) == action)

        total = self.session.exec(
            select(func.count()).select_from(TimelineEvent).where(*filters)
        ).one()
        order: ColumnElement[Any] = (
            desc(col(TimelineEvent.occurred_at))
            if descending
            else asc(col(TimelineEvent.occurred_at))
        )
        items = list(
            self.session.exec(
                select(TimelineEvent)
                .where(*filters)
                .order_by(order, col(TimelineEvent.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)
