from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import Attachment, AttachmentEntityLink, DomainEntityType
from app.repositories.base import PageResult
from app.repositories.revisioned import RevisionedRepository


class AttachmentRepository(RevisionedRepository[Attachment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Attachment, "attachment")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        entity_type: DomainEntityType | None,
        entity_id: UUID | None,
    ) -> PageResult[Attachment]:
        filters = [
            col(Attachment.workspace_id) == workspace_id,
            col(Attachment.deleted_at).is_(None),
        ]
        if entity_type is not None or entity_id is not None:
            link_query = select(AttachmentEntityLink.attachment_id).where(
                col(AttachmentEntityLink.workspace_id) == workspace_id
            )
            if entity_type is not None:
                link_query = link_query.where(col(AttachmentEntityLink.entity_type) == entity_type)
            if entity_id is not None:
                link_query = link_query.where(col(AttachmentEntityLink.entity_id) == entity_id)
            filters.append(col(Attachment.id).in_(link_query))
        total = self.session.exec(
            select(func.count()).select_from(Attachment).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(Attachment)
                .where(*filters)
                .order_by(col(Attachment.created_at).desc(), col(Attachment.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def links_for(self, attachment_ids: list[UUID]) -> dict[UUID, list[AttachmentEntityLink]]:
        result: dict[UUID, list[AttachmentEntityLink]] = {
            attachment_id: [] for attachment_id in attachment_ids
        }
        if not attachment_ids:
            return result
        links = self.session.exec(
            select(AttachmentEntityLink)
            .where(col(AttachmentEntityLink.attachment_id).in_(attachment_ids))
            .order_by(col(AttachmentEntityLink.created_at), col(AttachmentEntityLink.id))
        ).all()
        for link in links:
            result.setdefault(link.attachment_id, []).append(link)
        return result
