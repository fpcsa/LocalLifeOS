from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.schemas.common import (
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
    SortOrder,
)
from app.schemas.productivity import (
    NoteCreateRequest,
    NoteLinkRequest,
    NoteLinkResponse,
    NoteResponse,
    NoteUpdateRequest,
)
from app.services.notes import (
    add_note_link,
    create_note,
    delete_note,
    get_note,
    list_notes,
    remove_note_link,
    update_note,
)

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=ListEnvelope[NoteResponse])
def read_notes(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=255)] = None,
    daily_note_date: date | None = None,
    tag_id: UUID | None = None,
    sort: Literal[
        "created_at", "updated_at", "title", "daily_note_date", "relevance"
    ] = "updated_at",
    order: SortOrder = SortOrder.DESC,
) -> ListEnvelope[NoteResponse]:
    items, total = list_notes(
        session,
        page=page,
        page_size=page_size,
        query=query,
        daily_note_date=daily_note_date,
        tag_id=tag_id,
        sort=sort,
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


@router.post("", response_model=DataEnvelope[NoteResponse], status_code=status.HTTP_201_CREATED)
def post_note(
    create_data: NoteCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[NoteResponse]:
    return DataEnvelope(data=create_note(session, create_data))


@router.get("/{note_id}", response_model=DataEnvelope[NoteResponse])
def read_note(note_id: UUID, session: SessionDependency) -> DataEnvelope[NoteResponse]:
    return DataEnvelope(data=get_note(session, note_id))


@router.patch("/{note_id}", response_model=DataEnvelope[NoteResponse])
def patch_note(
    note_id: UUID,
    update_data: NoteUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[NoteResponse]:
    return DataEnvelope(data=update_note(session, note_id, update_data))


@router.delete("/{note_id}", response_model=DataEnvelope[DeletedResource])
def remove_note(
    note_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_note(session, note_id, revision))


@router.post(
    "/{note_id}/links",
    response_model=DataEnvelope[NoteLinkResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_note_link(
    note_id: UUID,
    create_data: NoteLinkRequest,
    session: SessionDependency,
) -> DataEnvelope[NoteLinkResponse]:
    return DataEnvelope(data=add_note_link(session, note_id, create_data))


@router.delete("/{note_id}/links/{link_id}", response_model=DataEnvelope[DeletedResource])
def remove_link(
    note_id: UUID,
    link_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=remove_note_link(session, note_id, link_id))
