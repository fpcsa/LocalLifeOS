from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import SessionDependency
from app.models import DomainEntityType
from app.schemas.common import DataEnvelope, DeletedResource, ListEnvelope, PaginationMeta
from app.schemas.productivity import AttachmentResponse
from app.services.attachments import (
    delete_attachment,
    get_attachment_file,
    list_attachments,
    upload_attachment,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("", response_model=ListEnvelope[AttachmentResponse])
def read_attachments(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    entity_type: DomainEntityType | None = None,
    entity_id: UUID | None = None,
) -> ListEnvelope[AttachmentResponse]:
    items, total = list_attachments(
        session,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        entity_id=entity_id,
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


@router.post(
    "",
    response_model=DataEnvelope[AttachmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def post_attachment(
    session: SessionDependency,
    file: Annotated[UploadFile, File()],
    entity_type: Annotated[DomainEntityType, Form()],
    entity_id: Annotated[UUID, Form()],
) -> DataEnvelope[AttachmentResponse]:
    return DataEnvelope(data=await upload_attachment(session, file, entity_type, entity_id))


@router.get("/{attachment_id}/download", response_class=FileResponse)
def download_attachment(attachment_id: UUID, session: SessionDependency) -> FileResponse:
    attachment, path = get_attachment_file(session, attachment_id)
    return FileResponse(
        path=path,
        media_type=attachment.media_type,
        filename=attachment.original_filename,
    )


@router.delete("/{attachment_id}", response_model=DataEnvelope[DeletedResource])
def remove_attachment(
    attachment_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_attachment(session, attachment_id, revision))
