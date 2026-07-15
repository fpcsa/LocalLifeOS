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
from app.schemas.resources import TagCreate, TagResponse
from app.services.tags import create_tag, delete_tag, list_tags

router = APIRouter(tags=["tags"])


@router.get("/tags", response_model=ListEnvelope[TagResponse])
def read_tags(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=80)] = None,
    sort: Literal["name", "created_at", "updated_at"] = "name",
    order: SortOrder = SortOrder.ASC,
) -> ListEnvelope[TagResponse]:
    result = list_tags(
        session,
        page=page,
        page_size=page_size,
        query=query,
        sort=sort,
        order=order,
    )
    total_pages = (result.total + page_size - 1) // page_size
    return ListEnvelope(
        data=[TagResponse.model_validate(tag) for tag in result.items],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=result.total,
            total_pages=total_pages,
        ),
    )


@router.post(
    "/tags",
    response_model=DataEnvelope[TagResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_tag(
    create_data: TagCreate,
    session: SessionDependency,
) -> DataEnvelope[TagResponse]:
    tag = create_tag(session, create_data)
    return DataEnvelope(data=TagResponse.model_validate(tag))


@router.delete("/tags/{tag_id}", response_model=DataEnvelope[DeletedResource])
def remove_tag(
    tag_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_tag(session, tag_id, revision))
