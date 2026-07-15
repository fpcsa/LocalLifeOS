from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDependency
from app.models import TaskPriority, TaskStatus
from app.schemas.common import (
    AwareDateTime,
    DataEnvelope,
    DeletedResource,
    ListEnvelope,
    PaginationMeta,
    SortOrder,
)
from app.schemas.productivity import (
    BulkCompleteRequest,
    BulkRescheduleRequest,
    RecurrenceOccurrenceResponse,
    TaskCreateRequest,
    TaskDependencyRequest,
    TaskDependencyResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from app.schemas.scheduling import (
    SchedulingPreviewResponse,
    SchedulingScopeInput,
)
from app.services.scheduling import preview_task_schedule
from app.services.tasks import (
    add_task_dependency,
    bulk_complete_tasks,
    bulk_reschedule_tasks,
    create_task,
    delete_task,
    expand_task_occurrences,
    get_task,
    list_tasks,
    remove_task_dependency,
    update_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/actions/bulk-complete", response_model=DataEnvelope[list[TaskResponse]])
def post_bulk_complete(
    request: BulkCompleteRequest,
    session: SessionDependency,
) -> DataEnvelope[list[TaskResponse]]:
    return DataEnvelope(data=bulk_complete_tasks(session, request))


@router.post("/actions/bulk-reschedule", response_model=DataEnvelope[list[TaskResponse]])
def post_bulk_reschedule(
    request: BulkRescheduleRequest,
    session: SessionDependency,
) -> DataEnvelope[list[TaskResponse]]:
    return DataEnvelope(data=bulk_reschedule_tasks(session, request))


@router.get("", response_model=ListEnvelope[TaskResponse])
def read_tasks(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query(alias="q", max_length=255)] = None,
    project_id: UUID | None = None,
    parent_task_id: UUID | None = None,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    tag_id: UUID | None = None,
    due_before: AwareDateTime | None = None,
    due_after: AwareDateTime | None = None,
    overdue: bool | None = None,
    blocked: bool | None = None,
    schedulable: bool | None = None,
    sort: Literal["created_at", "updated_at", "due_at", "priority", "title"] = "created_at",
    order: SortOrder = SortOrder.DESC,
) -> ListEnvelope[TaskResponse]:
    items, total = list_tasks(
        session,
        page=page,
        page_size=page_size,
        query=query,
        project_id=project_id,
        parent_task_id=parent_task_id,
        status=task_status,
        priority=priority,
        tag_id=tag_id,
        due_before=due_before,
        due_after=due_after,
        overdue=overdue,
        blocked=blocked,
        schedulable=schedulable,
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


@router.post("", response_model=DataEnvelope[TaskResponse], status_code=status.HTTP_201_CREATED)
def post_task(
    create_data: TaskCreateRequest,
    session: SessionDependency,
) -> DataEnvelope[TaskResponse]:
    return DataEnvelope(data=create_task(session, create_data))


@router.get("/{task_id}", response_model=DataEnvelope[TaskResponse])
def read_task(task_id: UUID, session: SessionDependency) -> DataEnvelope[TaskResponse]:
    return DataEnvelope(data=get_task(session, task_id))


@router.patch("/{task_id}", response_model=DataEnvelope[TaskResponse])
def patch_task(
    task_id: UUID,
    update_data: TaskUpdateRequest,
    session: SessionDependency,
) -> DataEnvelope[TaskResponse]:
    return DataEnvelope(data=update_task(session, task_id, update_data))


@router.delete("/{task_id}", response_model=DataEnvelope[DeletedResource])
def remove_task(
    task_id: UUID,
    session: SessionDependency,
    revision: Annotated[int, Query(ge=1)],
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=delete_task(session, task_id, revision))


@router.post(
    "/{task_id}/dependencies",
    response_model=DataEnvelope[TaskDependencyResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_task_dependency(
    task_id: UUID,
    create_data: TaskDependencyRequest,
    session: SessionDependency,
) -> DataEnvelope[TaskDependencyResponse]:
    return DataEnvelope(data=add_task_dependency(session, task_id, create_data))


@router.delete(
    "/{task_id}/dependencies/{dependency_id}",
    response_model=DataEnvelope[DeletedResource],
)
def remove_dependency(
    task_id: UUID,
    dependency_id: UUID,
    session: SessionDependency,
) -> DataEnvelope[DeletedResource]:
    return DataEnvelope(data=remove_task_dependency(session, task_id, dependency_id))


@router.get(
    "/{task_id}/occurrences",
    response_model=DataEnvelope[list[RecurrenceOccurrenceResponse]],
)
def read_task_occurrences(
    task_id: UUID,
    session: SessionDependency,
    start: AwareDateTime,
    end: AwareDateTime,
) -> DataEnvelope[list[RecurrenceOccurrenceResponse]]:
    return DataEnvelope(data=expand_task_occurrences(session, task_id, start, end))


@router.post(
    "/{task_id}/schedule-suggestions",
    response_model=DataEnvelope[SchedulingPreviewResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_task_schedule_suggestions(
    task_id: UUID,
    request: SchedulingScopeInput,
    session: SessionDependency,
) -> DataEnvelope[SchedulingPreviewResponse]:
    return DataEnvelope(data=preview_task_schedule(session, task_id, request))
