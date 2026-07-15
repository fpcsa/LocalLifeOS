from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.schemas.common import AwareDateTime, DataEnvelope
from app.schemas.scheduling import (
    CapacityReport,
    SchedulingApplyRequest,
    SchedulingApplyResponse,
    SchedulingExplanationResponse,
    SchedulingPolicyInput,
    SchedulingPreviewRequest,
    SchedulingPreviewResponse,
    SchedulingScopeInput,
)
from app.services.scheduling import (
    apply_scheduling_preview,
    create_scheduling_preview,
    get_capacity_report,
    get_scheduling_explanations,
)

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


@router.post(
    "/preview",
    response_model=DataEnvelope[SchedulingPreviewResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_scheduling_preview(
    request: SchedulingPreviewRequest,
    session: SessionDependency,
) -> DataEnvelope[SchedulingPreviewResponse]:
    return DataEnvelope(data=create_scheduling_preview(session, request))


@router.post(
    "/apply",
    response_model=DataEnvelope[SchedulingApplyResponse],
)
def post_scheduling_apply(
    request: SchedulingApplyRequest,
    session: SessionDependency,
) -> DataEnvelope[SchedulingApplyResponse]:
    return DataEnvelope(data=apply_scheduling_preview(session, request))


@router.get(
    "/capacity",
    response_model=DataEnvelope[CapacityReport],
)
def read_scheduling_capacity(
    session: SessionDependency,
    start: AwareDateTime,
    end: AwareDateTime,
    commitment_id: UUID | None = None,
    minimum_focus_block_minutes: Annotated[int, Query(ge=5, le=480)] = 30,
    maximum_scheduled_minutes_per_day: Annotated[int, Query(ge=30, le=1_440)] = 480,
) -> DataEnvelope[CapacityReport]:
    request = SchedulingScopeInput(
        planning_start_at=start,
        planning_end_at=end,
        policy=SchedulingPolicyInput(
            minimum_focus_block_minutes=minimum_focus_block_minutes,
            maximum_scheduled_minutes_per_day=maximum_scheduled_minutes_per_day,
        ),
    )
    return DataEnvelope(
        data=get_capacity_report(
            session,
            request,
            commitment_id=commitment_id,
        )
    )


@router.get(
    "/explanations/{preview_id}",
    response_model=DataEnvelope[SchedulingExplanationResponse],
)
def read_scheduling_explanations(
    preview_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[SchedulingExplanationResponse]:
    return DataEnvelope(data=get_scheduling_explanations(session, preview_id))
