from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import GoalStatus
from app.schemas.common import DataEnvelope, DeletedResource, ListEnvelope, PaginationMeta
from app.schemas.finance import GoalCreateRequest, GoalResponse, GoalUpdateRequest
from app.services.goals import create_goal, delete_goal, get_goal, list_goals, update_goal

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=ListEnvelope[GoalResponse])
def read_goals(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    goal_status: Annotated[GoalStatus | None, Query(alias="status")] = None,
) -> ListEnvelope[GoalResponse]:
    items, total = list_goals(
        session,
        page=page,
        page_size=page_size,
        status=goal_status,
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


@router.post("", response_model=DataEnvelope[GoalResponse], status_code=status.HTTP_201_CREATED)
def post_goal(
    create_data: GoalCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[GoalResponse]:
    return DataEnvelope(data=create_goal(session, create_data))


@router.get("/{goal_id}", response_model=DataEnvelope[GoalResponse])
def read_goal(goal_id: UUID, session: SessionDependency) -> DataEnvelope[GoalResponse]:
    return DataEnvelope(data=get_goal(session, goal_id))


@router.patch("/{goal_id}", response_model=DataEnvelope[GoalResponse])
def patch_goal(
    goal_id: UUID,
    update_data: GoalUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[GoalResponse]:
    return DataEnvelope(data=update_goal(session, goal_id, update_data))


@router.delete("/{goal_id}", response_model=DataEnvelope[DeletedResource])
def remove_goal(
    goal_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_goal(session, goal_id, revision))
