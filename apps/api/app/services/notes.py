from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import (
    DomainConflictError,
    DomainNotFoundError,
    DomainValidationError,
)
from app.db.transactions import transaction
from app.models import (
    CalendarEventEntityLink,
    CommitmentEntityType,
    DomainEntityType,
    Note,
    NoteEntityLink,
    NoteLink,
)
from app.repositories.notes import NoteRepository, NoteSort
from app.schemas.common import DeletedResource, SortOrder
from app.schemas.productivity import (
    DomainLinkResponse,
    NoteCreateRequest,
    NoteLinkRequest,
    NoteLinkResponse,
    NoteResponse,
    NoteUpdateRequest,
)
from app.services.domain_links import (
    remove_generic_links,
    replace_commitment_links,
    replace_note_entity_links,
    replace_tag_links,
)
from app.services.events import emit_timeline_event
from app.services.workspace import get_current_workspace

NOTE_LINK_TYPES = frozenset(
    {
        DomainEntityType.PROJECT,
        DomainEntityType.TASK,
        DomainEntityType.CALENDAR_EVENT,
        DomainEntityType.TRANSACTION,
        DomainEntityType.GOAL,
        DomainEntityType.BUDGET,
    }
)


def _note_responses(
    repository: NoteRepository,
    notes: list[Note],
) -> list[NoteResponse]:
    note_ids = [note.id for note in notes]
    outbound, backlinks = repository.links_for(note_ids)
    entity_links = repository.entity_links_for(note_ids)
    tag_ids = repository.tag_ids_for(note_ids)
    attachment_ids = repository.attachment_ids_for(note_ids)
    commitment_ids = repository.commitment_ids_for(note_ids)
    responses: list[NoteResponse] = []
    for note in notes:
        values = note.model_dump(exclude={"deleted_at"})
        responses.append(
            NoteResponse(
                **values,
                tag_ids=tag_ids.get(note.id, []),
                attachment_ids=attachment_ids.get(note.id, []),
                links=[NoteLinkResponse.model_validate(link) for link in outbound.get(note.id, [])],
                backlinks=[
                    NoteLinkResponse.model_validate(link) for link in backlinks.get(note.id, [])
                ],
                entity_links=[
                    DomainLinkResponse(
                        id=link.id,
                        entity_type=link.entity_type,
                        entity_id=link.entity_id,
                        label=link.label,
                        created_at=link.created_at,
                    )
                    for link in entity_links.get(note.id, [])
                ],
                commitment_ids=commitment_ids.get(note.id, []),
            )
        )
    return responses


def _ensure_daily_note_available(
    session: Session,
    workspace_id: UUID,
    daily_note_date: date | None,
    *,
    exclude_id: UUID | None = None,
) -> None:
    if daily_note_date is None:
        return
    statement = select(Note).where(
        col(Note.workspace_id) == workspace_id,
        col(Note.daily_note_date) == daily_note_date,
        col(Note.deleted_at).is_(None),
    )
    if exclude_id is not None:
        statement = statement.where(col(Note.id) != exclude_id)
    if session.exec(statement).first() is not None:
        raise DomainConflictError(
            "duplicate_daily_note",
            "A daily note already exists for this date.",
            {"daily_note_date": daily_note_date.isoformat()},
        )


def list_notes(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    daily_note_date: date | None,
    tag_id: UUID | None,
    sort: NoteSort,
    order: SortOrder,
) -> tuple[list[NoteResponse], int]:
    workspace = get_current_workspace(session)
    repository = NoteRepository(session)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        daily_note_date=daily_note_date,
        tag_id=tag_id,
        sort=sort,
        descending=order == SortOrder.DESC,
    )
    return _note_responses(repository, result.items), result.total


def get_note(session: Session, note_id: UUID) -> NoteResponse:
    workspace = get_current_workspace(session)
    repository = NoteRepository(session)
    note = repository.get_active(workspace.id, note_id)
    if note is None:
        raise DomainNotFoundError("note", note_id)
    return _note_responses(repository, [note])[0]


def create_note(session: Session, create_data: NoteCreateRequest) -> NoteResponse:
    workspace = get_current_workspace(session)
    repository = NoteRepository(session)
    _ensure_daily_note_available(session, workspace.id, create_data.daily_note_date)
    values = create_data.model_dump(exclude={"tag_ids", "entity_links", "commitment_ids"})
    with transaction(session):
        note = repository.add(Note(workspace_id=workspace.id, **values))
        replace_tag_links(
            session,
            workspace.id,
            DomainEntityType.NOTE,
            note.id,
            create_data.tag_ids,
        )
        replace_note_entity_links(
            session,
            workspace.id,
            note.id,
            create_data.entity_links,
            NOTE_LINK_TYPES,
        )
        replace_commitment_links(
            session,
            workspace.id,
            CommitmentEntityType.NOTE,
            note.id,
            create_data.commitment_ids,
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.NOTE,
            entity_id=note.id,
            action="note_created",
            title=f"Note created: {note.title}",
        )
    return _note_responses(repository, [note])[0]


def update_note(
    session: Session,
    note_id: UUID,
    update_data: NoteUpdateRequest,
) -> NoteResponse:
    workspace = get_current_workspace(session)
    repository = NoteRepository(session)
    current = repository.get_active(workspace.id, note_id)
    if current is None:
        raise DomainNotFoundError("note", note_id)
    fields = update_data.model_fields_set
    values = update_data.model_dump(
        exclude={"revision", "tag_ids", "entity_links", "commitment_ids"},
        exclude_unset=True,
    )
    if "daily_note_date" in fields:
        _ensure_daily_note_available(
            session,
            workspace.id,
            update_data.daily_note_date,
            exclude_id=note_id,
        )
    if (
        not values
        and "tag_ids" not in fields
        and "entity_links" not in fields
        and "commitment_ids" not in fields
    ):
        raise DomainValidationError("empty_update", "At least one note field is required.")
    with transaction(session):
        note = repository.update(workspace.id, note_id, update_data.revision, values)
        if update_data.tag_ids is not None:
            replace_tag_links(
                session,
                workspace.id,
                DomainEntityType.NOTE,
                note.id,
                update_data.tag_ids,
            )
        if update_data.entity_links is not None:
            replace_note_entity_links(
                session,
                workspace.id,
                note.id,
                update_data.entity_links,
                NOTE_LINK_TYPES,
            )
        if update_data.commitment_ids is not None:
            replace_commitment_links(
                session,
                workspace.id,
                CommitmentEntityType.NOTE,
                note.id,
                update_data.commitment_ids,
            )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.NOTE,
            entity_id=note.id,
            action="note_updated",
            title=f"Note updated: {note.title}",
            payload={"fields": sorted(fields - {"revision"})},
        )
    return _note_responses(repository, [note])[0]


def delete_note(session: Session, note_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = NoteRepository(session)
    current = repository.get_active(workspace.id, note_id)
    if current is None:
        raise DomainNotFoundError("note", note_id)
    with transaction(session):
        links = session.exec(
            select(NoteLink).where(
                (col(NoteLink.source_note_id) == note_id)
                | (col(NoteLink.target_note_id) == note_id)
            )
        ).all()
        for note_link in links:
            session.delete(note_link)
        own_entity_links = session.exec(
            select(NoteEntityLink).where(col(NoteEntityLink.note_id) == note_id)
        ).all()
        for entity_link in own_entity_links:
            session.delete(entity_link)
        calendar_links = session.exec(
            select(CalendarEventEntityLink).where(
                col(CalendarEventEntityLink.entity_type) == DomainEntityType.NOTE,
                col(CalendarEventEntityLink.entity_id) == note_id,
            )
        ).all()
        for calendar_link in calendar_links:
            session.delete(calendar_link)
        remove_generic_links(
            session,
            workspace.id,
            DomainEntityType.NOTE,
            CommitmentEntityType.NOTE,
            note_id,
        )
        note = repository.soft_delete(workspace.id, note_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.NOTE,
            entity_id=note.id,
            action="note_deleted",
            title=f"Note deleted: {note.title}",
        )
    return DeletedResource(id=note_id)


def add_note_link(
    session: Session,
    source_note_id: UUID,
    create_data: NoteLinkRequest,
) -> NoteLinkResponse:
    workspace = get_current_workspace(session)
    repository = NoteRepository(session)
    source = repository.get_active(workspace.id, source_note_id)
    target = repository.get_active(workspace.id, create_data.target_note_id)
    if source is None:
        raise DomainNotFoundError("note", source_note_id)
    if target is None:
        raise DomainNotFoundError("note", create_data.target_note_id)
    if source.id == target.id:
        raise DomainValidationError("note_link_self", "A note cannot link to itself.")
    duplicate = session.exec(
        select(NoteLink).where(
            col(NoteLink.source_note_id) == source.id,
            col(NoteLink.target_note_id) == target.id,
        )
    ).first()
    if duplicate is not None:
        raise DomainConflictError("duplicate_note_link", "This note link already exists.")
    with transaction(session):
        link = NoteLink(
            workspace_id=workspace.id,
            source_note_id=source.id,
            target_note_id=target.id,
            label=create_data.label,
        )
        session.add(link)
        session.flush()
        session.refresh(link)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.NOTE,
            entity_id=source.id,
            action="note_link_added",
            title=f"Note link added: {source.title} → {target.title}",
            payload={"target_note_id": str(target.id)},
        )
    return NoteLinkResponse.model_validate(link)


def remove_note_link(
    session: Session,
    source_note_id: UUID,
    link_id: UUID,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    source = NoteRepository(session).get_active(workspace.id, source_note_id)
    if source is None:
        raise DomainNotFoundError("note", source_note_id)
    link = session.exec(
        select(NoteLink).where(
            col(NoteLink.id) == link_id,
            col(NoteLink.workspace_id) == workspace.id,
            col(NoteLink.source_note_id) == source_note_id,
        )
    ).first()
    if link is None:
        raise DomainNotFoundError("note_link", link_id)
    with transaction(session):
        session.delete(link)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.NOTE,
            entity_id=source.id,
            action="note_link_removed",
            title=f"Note link removed from: {source.title}",
        )
    return DeletedResource(id=link_id)
