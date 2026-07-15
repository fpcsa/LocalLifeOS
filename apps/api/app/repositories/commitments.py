from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models import Commitment, CommitmentEntityLink, CommitmentStatus
from app.repositories.base import PageResult
from app.repositories.revisioned import RevisionedRepository


class CommitmentRepository(RevisionedRepository[Commitment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Commitment, "commitment")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        query: str | None,
        status: CommitmentStatus | None,
        category: str | None,
        target_before: datetime | None,
        include_archived: bool,
    ) -> PageResult[Commitment]:
        filters: list[ColumnElement[bool]] = [
            col(Commitment.workspace_id) == workspace_id,
            col(Commitment.deleted_at).is_(None),
        ]
        if not include_archived:
            filters.append(col(Commitment.status) != CommitmentStatus.ARCHIVED)
        if query:
            filters.append(col(Commitment.title).ilike(f"%{query.strip()}%"))
        if status is not None:
            filters.append(col(Commitment.status) == status)
        if category:
            filters.append(col(Commitment.category) == category)
        if target_before is not None:
            filters.append(col(Commitment.ends_at) <= target_before)
        total = self.session.exec(
            select(func.count()).select_from(Commitment).where(*filters)
        ).one()
        items = list(
            self.session.exec(
                select(Commitment)
                .where(*filters)
                .order_by(
                    col(Commitment.ends_at).is_(None),
                    col(Commitment.ends_at),
                    col(Commitment.created_at),
                    col(Commitment.id),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def links_for(self, commitment_ids: list[UUID]) -> dict[UUID, list[CommitmentEntityLink]]:
        result: dict[UUID, list[CommitmentEntityLink]] = {
            commitment_id: [] for commitment_id in commitment_ids
        }
        if not commitment_ids:
            return result
        links = self.session.exec(
            select(CommitmentEntityLink)
            .where(col(CommitmentEntityLink.commitment_id).in_(commitment_ids))
            .order_by(
                col(CommitmentEntityLink.created_at),
                col(CommitmentEntityLink.id),
            )
        ).all()
        for link in links:
            result.setdefault(link.commitment_id, []).append(link)
        return result

    def link(
        self, workspace_id: UUID, commitment_id: UUID, link_id: UUID
    ) -> CommitmentEntityLink | None:
        return self.session.exec(
            select(CommitmentEntityLink).where(
                col(CommitmentEntityLink.workspace_id) == workspace_id,
                col(CommitmentEntityLink.commitment_id) == commitment_id,
                col(CommitmentEntityLink.id) == link_id,
            )
        ).first()
