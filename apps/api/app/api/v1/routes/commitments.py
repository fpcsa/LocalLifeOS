from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import CommitmentStatus
from app.schemas.commitments import (
    CommitmentAssessmentResponse,
    CommitmentCreateRequest,
    CommitmentImpactResponse,
    CommitmentLinkCreateRequest,
    CommitmentLinkResponse,
    CommitmentResponse,
    CommitmentRevisionRequest,
    CommitmentUpdateRequest,
    CommitmentWarningsResponse,
    UnifiedTimelineEntityType,
    UnifiedTimelineItem,
)
from app.schemas.common import (
    AwareDateTime,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
    SortOrder,
)
from app.schemas.scheduling import SchedulingPreviewResponse, SchedulingScopeInput
from app.services.commitment_engine import (
    assess_commitment,
    get_commitment_impact,
    get_commitment_warnings,
)
from app.services.commitment_management import (
    archive_commitment,
    create_commitment,
    create_commitment_link,
    delete_commitment,
    delete_commitment_link,
    get_commitment,
    list_commitment_links,
    list_commitments,
    update_commitment,
)
from app.services.scheduling import preview_commitment_schedule
from app.services.unified_timeline import list_unified_timeline

router = APIRouter(prefix="/commitments", tags=["commitments"])


@router.get("", response_model=ListEnvelope[CommitmentResponse])
def read_commitments(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=255)] = None,
    commitment_status: Annotated[CommitmentStatus | None, Query(alias="status")] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    target_before: AwareDateTime | None = None,
    include_archived: bool = False,
) -> ListEnvelope[CommitmentResponse]:
    items, total = list_commitments(
        session,
        page=page,
        page_size=page_size,
        query=query,
        status=commitment_status,
        category=category,
        target_before=target_before,
        include_archived=include_archived,
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
    response_model=DataEnvelope[CommitmentResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_commitment(
    create_data: CommitmentCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[CommitmentResponse]:
    return DataEnvelope(data=create_commitment(session, create_data))


@router.get("/{commitment_id}", response_model=DataEnvelope[CommitmentResponse])
def read_commitment(
    commitment_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[CommitmentResponse]:
    return DataEnvelope(data=get_commitment(session, commitment_id))


@router.patch("/{commitment_id}", response_model=DataEnvelope[CommitmentResponse])
def patch_commitment(
    commitment_id: UUID,
    update_data: CommitmentUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[CommitmentResponse]:
    return DataEnvelope(data=update_commitment(session, commitment_id, update_data))


@router.delete("/{commitment_id}", response_model=DataEnvelope[DeletedResource])
def remove_commitment(
    commitment_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_commitment(session, commitment_id, revision))


@router.post("/{commitment_id}/archive", response_model=DataEnvelope[CommitmentResponse])
def post_commitment_archive(
    commitment_id: UUID,
    request: CommitmentRevisionRequest,
    session: SessionDependency,
) -> DataEnvelope[CommitmentResponse]:
    return DataEnvelope(data=archive_commitment(session, commitment_id, request.revision))


@router.get(
    "/{commitment_id}/links",
    response_model=DataEnvelope[list[CommitmentLinkResponse]],
)
def read_commitment_links(
    commitment_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[list[CommitmentLinkResponse]]:
    return DataEnvelope(data=list_commitment_links(session, commitment_id))


@router.post(
    "/{commitment_id}/links",
    response_model=DataEnvelope[CommitmentLinkResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_commitment_link(
    commitment_id: UUID,
    create_data: CommitmentLinkCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[CommitmentLinkResponse]:
    return DataEnvelope(data=create_commitment_link(session, commitment_id, create_data))


@router.delete(
    "/{commitment_id}/links/{link_id}",
    response_model=DataEnvelope[DeletedResource],
)
def remove_commitment_link(
    commitment_id: UUID,
    link_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_commitment_link(session, commitment_id, link_id))


@router.get(
    "/{commitment_id}/assessment",
    response_model=DataEnvelope[CommitmentAssessmentResponse],
)
def read_commitment_assessment(
    commitment_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[CommitmentAssessmentResponse]:
    return DataEnvelope(data=assess_commitment(session, commitment_id))


@router.get(
    "/{commitment_id}/impact",
    response_model=DataEnvelope[CommitmentImpactResponse],
)
def read_commitment_impact(
    commitment_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[CommitmentImpactResponse]:
    return DataEnvelope(data=get_commitment_impact(session, commitment_id))


@router.get(
    "/{commitment_id}/warnings",
    response_model=DataEnvelope[CommitmentWarningsResponse],
)
def read_commitment_warnings(
    commitment_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[CommitmentWarningsResponse]:
    return DataEnvelope(data=get_commitment_warnings(session, commitment_id))


@router.get(
    "/{commitment_id}/timeline",
    response_model=ListEnvelope[UnifiedTimelineItem],
)
def read_commitment_timeline(
    commitment_id: UUID,
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    start: AwareDateTime | None = None,
    end: AwareDateTime | None = None,
    entity_type: UnifiedTimelineEntityType | None = None,
    entity_id: UUID | None = None,
    order: SortOrder = SortOrder.DESC,
) -> ListEnvelope[UnifiedTimelineItem]:
    items, total = list_unified_timeline(
        session,
        page=page,
        page_size=page_size,
        start=start,
        end=end,
        entity_type=entity_type,
        entity_id=entity_id,
        order=order,
        commitment_id=commitment_id,
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
    "/{commitment_id}/refresh",
    response_model=DataEnvelope[CommitmentAssessmentResponse],
)
def post_commitment_refresh(
    commitment_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[CommitmentAssessmentResponse]:
    return DataEnvelope(data=assess_commitment(session, commitment_id))


@router.post(
    "/{commitment_id}/schedule-preview",
    response_model=DataEnvelope[SchedulingPreviewResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_commitment_schedule_preview(
    commitment_id: UUID,
    request: SchedulingScopeInput,
    session: SessionDependency,
) -> DataEnvelope[SchedulingPreviewResponse]:
    return DataEnvelope(data=preview_commitment_schedule(session, commitment_id, request))
