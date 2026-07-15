from __future__ import annotations

from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import asc, desc, func, update
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.core.exceptions import DomainNotFoundError, RevisionConflictError
from app.models import Tag
from app.models.common import utc_now
from app.repositories.base import PageResult

TagSort = Literal["name", "created_at", "updated_at"]


class TagRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, workspace_id: UUID, tag_id: UUID) -> Tag | None:
        return self.session.exec(
            select(Tag).where(
                col(Tag.id) == tag_id,
                col(Tag.workspace_id) == workspace_id,
                col(Tag.deleted_at).is_(None),
            )
        ).first()

    def find_by_name(self, workspace_id: UUID, name: str) -> Tag | None:
        return self.session.exec(
            select(Tag).where(
                col(Tag.workspace_id) == workspace_id,
                func.lower(col(Tag.name)) == name.strip().lower(),
                col(Tag.deleted_at).is_(None),
            )
        ).first()

    def add(self, tag: Tag) -> Tag:
        self.session.add(tag)
        self.session.flush()
        self.session.refresh(tag)
        return tag

    def list(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        query: str | None,
        sort: TagSort,
        descending: bool,
    ) -> PageResult[Tag]:
        filters: list[ColumnElement[bool]] = [
            col(Tag.workspace_id) == workspace_id,
            col(Tag.deleted_at).is_(None),
        ]
        if query:
            filters.append(col(Tag.name).ilike(f"%{query.strip()}%"))

        total = self.session.exec(select(func.count()).select_from(Tag).where(*filters)).one()
        sort_column = cast(
            ColumnElement[Any],
            {
                "name": func.lower(col(Tag.name)),
                "created_at": col(Tag.created_at),
                "updated_at": col(Tag.updated_at),
            }[sort],
        )
        order: ColumnElement[Any] = desc(sort_column) if descending else asc(sort_column)
        items = list(
            self.session.exec(
                select(Tag)
                .where(*filters)
                .order_by(order, col(Tag.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def soft_delete(self, workspace_id: UUID, tag_id: UUID, expected_revision: int) -> Tag:
        now = utc_now()
        result = self.session.execute(
            update(Tag)
            .where(
                col(Tag.id) == tag_id,
                col(Tag.workspace_id) == workspace_id,
                col(Tag.revision) == expected_revision,
                col(Tag.deleted_at).is_(None),
            )
            .values(
                deleted_at=now,
                updated_at=now,
                revision=expected_revision + 1,
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            self.session.expire_all()
            latest = self.session.get(Tag, tag_id)
            if (
                latest is None
                or latest.workspace_id != workspace_id
                or latest.deleted_at is not None
            ):
                raise DomainNotFoundError("tag", tag_id)
            raise RevisionConflictError("tag", expected_revision, latest.revision)

        self.session.expire_all()
        deleted = self.session.get(Tag, tag_id)
        if deleted is None:
            raise DomainNotFoundError("tag", tag_id)
        return deleted
