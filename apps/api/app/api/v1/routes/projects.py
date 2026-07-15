from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import ProjectStatus
from app.schemas.common import DataEnvelope, ListEnvelope, PaginationMeta, SortOrder
from app.schemas.productivity import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
    RevisionRequest,
)
from app.services.projects import (
    archive_project,
    create_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ListEnvelope[ProjectResponse])
def read_projects(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=160)] = None,
    project_status: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    target_before: date | None = None,
    sort: Literal["name", "created_at", "updated_at", "target_end_date"] = "updated_at",
    order: SortOrder = SortOrder.DESC,
) -> ListEnvelope[ProjectResponse]:
    items, total = list_projects(
        session,
        page=page,
        page_size=page_size,
        query=query,
        status=project_status,
        target_before=target_before,
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


@router.post("", response_model=DataEnvelope[ProjectResponse], status_code=status.HTTP_201_CREATED)
def post_project(
    create_data: ProjectCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[ProjectResponse]:
    return DataEnvelope(data=create_project(session, create_data))


@router.get("/{project_id}", response_model=DataEnvelope[ProjectResponse])
def read_project(project_id: UUID, session: SessionDependency) -> DataEnvelope[ProjectResponse]:
    return DataEnvelope(data=get_project(session, project_id))


@router.patch("/{project_id}", response_model=DataEnvelope[ProjectResponse])
def patch_project(
    project_id: UUID,
    update_data: ProjectUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[ProjectResponse]:
    return DataEnvelope(data=update_project(session, project_id, update_data))


@router.post("/{project_id}/archive", response_model=DataEnvelope[ProjectResponse])
def post_project_archive(
    project_id: UUID,
    request: RevisionRequest,
    session: SessionDependency,
) -> DataEnvelope[ProjectResponse]:
    return DataEnvelope(data=archive_project(session, project_id, request.revision))
