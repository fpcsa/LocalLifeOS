from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import and_, or_
from sqlmodel import Session, col, select

from app.models import (
    AttachmentEntityLink,
    CalendarEvent,
    CalendarEventEntityLink,
    CalendarEventStatus,
    CommitmentEntityLink,
    CommitmentEntityType,
    DomainEntityType,
)
from app.repositories.revisioned import RevisionedRepository


class CalendarEventRepository(RevisionedRepository[CalendarEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CalendarEvent, "calendar_event")

    def list_candidates(
        self,
        workspace_id: UUID,
        *,
        range_start: datetime,
        range_end: datetime,
        local_start_date: date,
        local_end_date: date,
        query: str | None,
        category: str | None,
        status: CalendarEventStatus | None,
    ) -> list[CalendarEvent]:
        filters = [
            col(CalendarEvent.workspace_id) == workspace_id,
            col(CalendarEvent.deleted_at).is_(None),
            or_(
                and_(
                    col(CalendarEvent.all_day).is_(False),
                    col(CalendarEvent.starts_at) < range_end,
                    col(CalendarEvent.ends_at) > range_start,
                ),
                and_(
                    col(CalendarEvent.all_day).is_(True),
                    col(CalendarEvent.all_day_start) < local_end_date,
                    col(CalendarEvent.all_day_end) > local_start_date,
                ),
                col(CalendarEvent.recurrence_rrule).is_not(None),
            ),
        ]
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    col(CalendarEvent.title).ilike(pattern),
                    col(CalendarEvent.description_markdown).ilike(pattern),
                    col(CalendarEvent.location).ilike(pattern),
                )
            )
        if category:
            filters.append(col(CalendarEvent.category) == category)
        if status is not None:
            filters.append(col(CalendarEvent.status) == status)
        return list(
            self.session.exec(
                select(CalendarEvent)
                .where(*filters)
                .order_by(
                    col(CalendarEvent.all_day_start),
                    col(CalendarEvent.starts_at),
                    col(CalendarEvent.id),
                )
            ).all()
        )

    def entity_links_for(
        self,
        event_ids: list[UUID],
    ) -> dict[UUID, list[CalendarEventEntityLink]]:
        result: dict[UUID, list[CalendarEventEntityLink]] = {event_id: [] for event_id in event_ids}
        if not event_ids:
            return result
        links = self.session.exec(
            select(CalendarEventEntityLink)
            .where(col(CalendarEventEntityLink.calendar_event_id).in_(event_ids))
            .order_by(col(CalendarEventEntityLink.created_at), col(CalendarEventEntityLink.id))
        ).all()
        for link in links:
            result.setdefault(link.calendar_event_id, []).append(link)
        return result

    def commitment_ids_for(self, event_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {event_id: [] for event_id in event_ids}
        if not event_ids:
            return result
        rows = self.session.exec(
            select(
                CommitmentEntityLink.entity_id,
                CommitmentEntityLink.commitment_id,
            ).where(
                col(CommitmentEntityLink.entity_type) == CommitmentEntityType.CALENDAR_EVENT,
                col(CommitmentEntityLink.entity_id).in_(event_ids),
            )
        ).all()
        for event_id, commitment_id in rows:
            result.setdefault(event_id, []).append(commitment_id)
        return result

    def attachment_ids_for(self, event_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {event_id: [] for event_id in event_ids}
        if not event_ids:
            return result
        rows = self.session.exec(
            select(AttachmentEntityLink.entity_id, AttachmentEntityLink.attachment_id).where(
                col(AttachmentEntityLink.entity_type) == DomainEntityType.CALENDAR_EVENT,
                col(AttachmentEntityLink.entity_id).in_(event_ids),
            )
        ).all()
        for event_id, attachment_id in rows:
            result.setdefault(event_id, []).append(attachment_id)
        return result
