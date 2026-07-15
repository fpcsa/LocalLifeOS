from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import asc, desc, func, text
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models import (
    AttachmentEntityLink,
    CommitmentEntityLink,
    CommitmentEntityType,
    DomainEntityType,
    Note,
    NoteEntityLink,
    NoteLink,
    TagEntityLink,
)
from app.repositories.base import PageResult
from app.repositories.revisioned import RevisionedRepository

NoteSort = Literal["created_at", "updated_at", "title", "daily_note_date", "relevance"]
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def _fts_query(value: str) -> str:
    tokens = TOKEN_PATTERN.findall(value)
    return " AND ".join(f'"{token}"*' for token in tokens)


class NoteRepository(RevisionedRepository[Note]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Note, "note")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        query: str | None,
        daily_note_date: date | None,
        tag_id: UUID | None,
        sort: NoteSort,
        descending: bool,
    ) -> PageResult[Note]:
        ranked_ids: list[UUID] | None = None
        if query:
            search_query = _fts_query(query)
            if not search_query:
                return PageResult(items=[], total=0)
            raw_ids = self.session.execute(
                text(
                    "SELECT note_id FROM notes_fts "
                    "WHERE workspace_id = :workspace_id AND notes_fts MATCH :query "
                    "ORDER BY bm25(notes_fts), note_id"
                ),
                {"workspace_id": workspace_id.hex, "query": search_query},
            ).scalars()
            ranked_ids = [UUID(hex=str(value)) for value in raw_ids]
            if not ranked_ids:
                return PageResult(items=[], total=0)

        filters: list[ColumnElement[bool]] = [
            col(Note.workspace_id) == workspace_id,
            col(Note.deleted_at).is_(None),
        ]
        if ranked_ids is not None:
            filters.append(col(Note.id).in_(ranked_ids))
        if daily_note_date is not None:
            filters.append(col(Note.daily_note_date) == daily_note_date)
        if tag_id is not None:
            filters.append(
                col(Note.id).in_(
                    select(TagEntityLink.entity_id).where(
                        col(TagEntityLink.workspace_id) == workspace_id,
                        col(TagEntityLink.tag_id) == tag_id,
                        col(TagEntityLink.entity_type) == DomainEntityType.NOTE,
                    )
                )
            )

        if ranked_ids is not None and sort == "relevance":
            matched = list(self.session.exec(select(Note).where(*filters)).all())
            by_id = {note.id: note for note in matched}
            ordered = [by_id[note_id] for note_id in ranked_ids if note_id in by_id]
            total = len(ordered)
            start = (page - 1) * page_size
            return PageResult(items=ordered[start : start + page_size], total=total)

        total = self.session.exec(select(func.count()).select_from(Note).where(*filters)).one()
        sort_column = cast(
            ColumnElement[Any],
            {
                "created_at": col(Note.created_at),
                "updated_at": col(Note.updated_at),
                "title": func.lower(col(Note.title)),
                "daily_note_date": col(Note.daily_note_date),
                "relevance": col(Note.updated_at),
            }[sort],
        )
        order = desc(sort_column) if descending else asc(sort_column)
        items = list(
            self.session.exec(
                select(Note)
                .where(*filters)
                .order_by(order, col(Note.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def links_for(
        self, note_ids: list[UUID]
    ) -> tuple[dict[UUID, list[NoteLink]], dict[UUID, list[NoteLink]]]:
        outbound: dict[UUID, list[NoteLink]] = {note_id: [] for note_id in note_ids}
        backlinks: dict[UUID, list[NoteLink]] = {note_id: [] for note_id in note_ids}
        if not note_ids:
            return outbound, backlinks
        links = self.session.exec(
            select(NoteLink)
            .where(
                (col(NoteLink.source_note_id).in_(note_ids))
                | (col(NoteLink.target_note_id).in_(note_ids))
            )
            .order_by(col(NoteLink.created_at), col(NoteLink.id))
        ).all()
        for link in links:
            if link.source_note_id in outbound:
                outbound[link.source_note_id].append(link)
            if link.target_note_id in backlinks:
                backlinks[link.target_note_id].append(link)
        return outbound, backlinks

    def entity_links_for(self, note_ids: list[UUID]) -> dict[UUID, list[NoteEntityLink]]:
        result: dict[UUID, list[NoteEntityLink]] = {note_id: [] for note_id in note_ids}
        if not note_ids:
            return result
        links = self.session.exec(
            select(NoteEntityLink)
            .where(col(NoteEntityLink.note_id).in_(note_ids))
            .order_by(col(NoteEntityLink.created_at), col(NoteEntityLink.id))
        ).all()
        for link in links:
            result.setdefault(link.note_id, []).append(link)
        return result

    def tag_ids_for(self, note_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {note_id: [] for note_id in note_ids}
        if not note_ids:
            return result
        rows = self.session.exec(
            select(TagEntityLink.entity_id, TagEntityLink.tag_id).where(
                col(TagEntityLink.entity_type) == DomainEntityType.NOTE,
                col(TagEntityLink.entity_id).in_(note_ids),
            )
        ).all()
        for note_id, tag_id in rows:
            result.setdefault(note_id, []).append(tag_id)
        return result

    def attachment_ids_for(self, note_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {note_id: [] for note_id in note_ids}
        if not note_ids:
            return result
        rows = self.session.exec(
            select(AttachmentEntityLink.entity_id, AttachmentEntityLink.attachment_id).where(
                col(AttachmentEntityLink.entity_type) == DomainEntityType.NOTE,
                col(AttachmentEntityLink.entity_id).in_(note_ids),
            )
        ).all()
        for note_id, attachment_id in rows:
            result.setdefault(note_id, []).append(attachment_id)
        return result

    def commitment_ids_for(self, note_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {note_id: [] for note_id in note_ids}
        if not note_ids:
            return result
        rows = self.session.exec(
            select(
                CommitmentEntityLink.entity_id,
                CommitmentEntityLink.commitment_id,
            ).where(
                col(CommitmentEntityLink.entity_type) == CommitmentEntityType.NOTE,
                col(CommitmentEntityLink.entity_id).in_(note_ids),
            )
        ).all()
        for note_id, commitment_id in rows:
            result.setdefault(note_id, []).append(commitment_id)
        return result
