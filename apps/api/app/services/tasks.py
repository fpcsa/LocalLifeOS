from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import update
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
    NoteEntityLink,
    Project,
    ProjectStatus,
    Task,
    TaskDependency,
    TaskPriority,
    TaskStatus,
)
from app.repositories.tasks import TaskRepository, TaskSort
from app.schemas.common import DeletedResource, SortOrder
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
from app.services.domain_links import (
    remove_generic_links,
    replace_commitment_links,
    replace_tag_links,
)
from app.services.events import emit_timeline_event
from app.services.recurrence import recurrence_values
from app.services.workspace import get_current_workspace
from app.utils.recurrence import expand_recurrence

ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.TODO: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED}
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {TaskStatus.TODO, TaskStatus.COMPLETED, TaskStatus.CANCELLED}
    ),
    TaskStatus.COMPLETED: frozenset({TaskStatus.TODO}),
    TaskStatus.CANCELLED: frozenset({TaskStatus.TODO}),
}


def _require_project(
    session: Session, workspace_id: UUID, project_id: UUID | None
) -> Project | None:
    if project_id is None:
        return None
    project = session.get(Project, project_id)
    if project is None or project.workspace_id != workspace_id or project.deleted_at is not None:
        raise DomainNotFoundError("project", project_id)
    if project.status == ProjectStatus.ARCHIVED:
        raise DomainValidationError(
            "archived_project",
            "Tasks cannot be assigned to an archived project.",
        )
    return project


def _validate_parent(
    repository: TaskRepository,
    workspace_id: UUID,
    task_id: UUID | None,
    parent_id: UUID | None,
    project_id: UUID | None,
) -> Task | None:
    if parent_id is None:
        return None
    parent = repository.get_active(workspace_id, parent_id)
    if parent is None:
        raise DomainNotFoundError("parent_task", parent_id)
    if task_id == parent.id:
        raise DomainValidationError("task_parent_cycle", "A task cannot be its own parent.")
    if project_id is not None and parent.project_id != project_id:
        raise DomainValidationError(
            "task_project_mismatch",
            "A subtask must belong to the same project as its parent.",
        )
    cursor = parent
    visited: set[UUID] = set()
    while cursor.parent_task_id is not None:
        if cursor.id in visited:
            raise DomainConflictError(
                "task_parent_cycle", "The existing task tree contains a cycle."
            )
        visited.add(cursor.id)
        if cursor.parent_task_id == task_id:
            raise DomainValidationError(
                "task_parent_cycle",
                "This parent assignment would create a task cycle.",
            )
        next_parent = repository.get_active(workspace_id, cursor.parent_task_id)
        if next_parent is None:
            break
        cursor = next_parent
    return parent


def _validate_status_transition(current: TaskStatus, target: TaskStatus) -> None:
    if target == current:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        raise DomainValidationError(
            "invalid_task_status_transition",
            f"Task status cannot change from {current.value} to {target.value}.",
        )


def _task_responses(
    session: Session,
    repository: TaskRepository,
    tasks: list[Task],
    *,
    now: datetime | None = None,
) -> list[TaskResponse]:
    task_ids = [task.id for task in tasks]
    dependencies = repository.dependencies_for(task_ids)
    dependency_ids = {
        dependency.depends_on_task_id
        for task_dependencies in dependencies.values()
        for dependency in task_dependencies
    }
    dependency_tasks = (
        session.exec(select(Task).where(col(Task.id).in_(dependency_ids))).all()
        if dependency_ids
        else []
    )
    dependency_status = {task.id: task.status for task in dependency_tasks}
    tag_ids = repository.tag_ids_for(task_ids)
    commitment_ids = repository.commitment_ids_for(task_ids)
    child_counts = repository.child_counts(task_ids)
    current_time = now or datetime.now(UTC)

    responses: list[TaskResponse] = []
    for task in tasks:
        task_dependencies = dependencies.get(task.id, [])
        blocked = any(
            (
                dependency.dependency_type.value == "finish_to_start"
                and dependency_status.get(dependency.depends_on_task_id) != TaskStatus.COMPLETED
            )
            or (
                dependency.dependency_type.value == "start_to_start"
                and dependency_status.get(dependency.depends_on_task_id) == TaskStatus.TODO
            )
            for dependency in task_dependencies
        )
        active = task.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
        overdue = active and task.due_at is not None and task.due_at < current_time
        schedulable = (
            active
            and not blocked
            and task.estimated_duration_minutes is not None
            and task.scheduled_start_at is None
        )
        values = task.model_dump(
            exclude={
                "deleted_at",
                "recurrence_frequency",
                "recurrence_interval",
                "recurrence_days_of_week",
                "recurrence_end_at",
            }
        )
        responses.append(
            TaskResponse(
                **values,
                tag_ids=tag_ids.get(task.id, []),
                commitment_ids=commitment_ids.get(task.id, []),
                dependencies=[
                    TaskDependencyResponse.model_validate(dependency)
                    for dependency in task_dependencies
                ],
                child_count=child_counts.get(task.id, 0),
                overdue=overdue,
                blocked=blocked,
                schedulable=schedulable,
            )
        )
    return responses


def list_tasks(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    project_id: UUID | None,
    parent_task_id: UUID | None,
    status: TaskStatus | None,
    priority: TaskPriority | None,
    tag_id: UUID | None,
    due_before: datetime | None,
    due_after: datetime | None,
    overdue: bool | None,
    blocked: bool | None,
    schedulable: bool | None,
    sort: TaskSort,
    order: SortOrder,
) -> tuple[list[TaskResponse], int]:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    now = datetime.now(UTC)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        project_id=project_id,
        parent_task_id=parent_task_id,
        status=status,
        priority=priority,
        tag_id=tag_id,
        due_before=due_before,
        due_after=due_after,
        overdue=overdue,
        blocked=blocked,
        schedulable=schedulable,
        now=now,
        sort=sort,
        descending=order == SortOrder.DESC,
    )
    return _task_responses(session, repository, result.items, now=now), result.total


def get_task(session: Session, task_id: UUID) -> TaskResponse:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    task = repository.get_active(workspace.id, task_id)
    if task is None:
        raise DomainNotFoundError("task", task_id)
    return _task_responses(session, repository, [task])[0]


def create_task(session: Session, create_data: TaskCreateRequest) -> TaskResponse:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    project = _require_project(session, workspace.id, create_data.project_id)
    parent = _validate_parent(
        repository,
        workspace.id,
        None,
        create_data.parent_task_id,
        create_data.project_id,
    )
    project_id = create_data.project_id
    if parent is not None and project_id is None:
        project_id = parent.project_id
        project = _require_project(session, workspace.id, project_id)
    del project

    values = create_data.model_dump(
        exclude={"tag_ids", "commitment_ids", "recurrence", "project_id"}
    )
    values["project_id"] = project_id
    values.update(recurrence_values(create_data.recurrence))
    if create_data.status == TaskStatus.COMPLETED:
        values["completed_at"] = datetime.now(UTC)

    with transaction(session):
        task = repository.add(Task(workspace_id=workspace.id, **values))
        replace_tag_links(
            session,
            workspace.id,
            DomainEntityType.TASK,
            task.id,
            create_data.tag_ids,
        )
        replace_commitment_links(
            session,
            workspace.id,
            CommitmentEntityType.TASK,
            task.id,
            create_data.commitment_ids,
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TASK,
            entity_id=task.id,
            action="task_created",
            title=f"Task created: {task.title}",
        )
    return _task_responses(session, repository, [task])[0]


def update_task(
    session: Session,
    task_id: UUID,
    update_data: TaskUpdateRequest,
) -> TaskResponse:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    current = repository.get_active(workspace.id, task_id)
    if current is None:
        raise DomainNotFoundError("task", task_id)

    fields = update_data.model_fields_set
    values = update_data.model_dump(
        exclude={"revision", "tag_ids", "commitment_ids", "recurrence"},
        exclude_unset=True,
    )
    project_id = values.get("project_id", current.project_id)
    _require_project(session, workspace.id, project_id)
    parent_id = values.get("parent_task_id", current.parent_task_id)
    parent = _validate_parent(repository, workspace.id, task_id, parent_id, project_id)
    if parent is not None and project_id is None:
        values["project_id"] = parent.project_id
        project_id = parent.project_id
    if parent is not None and parent.project_id != project_id:
        raise DomainValidationError(
            "task_project_mismatch",
            "A subtask must belong to the same project as its parent.",
        )

    earliest_start_at = values.get("earliest_start_at", current.earliest_start_at)
    due_at = values.get("due_at", current.due_at)
    if (
        isinstance(earliest_start_at, datetime)
        and isinstance(due_at, datetime)
        and earliest_start_at >= due_at
    ):
        raise DomainValidationError(
            "invalid_task_scheduling_range",
            "earliest_start_at must be before due_at.",
        )

    if "status" in fields and update_data.status is not None:
        _validate_status_transition(current.status, update_data.status)
        values["completed_at"] = (
            datetime.now(UTC) if update_data.status == TaskStatus.COMPLETED else None
        )
    if "recurrence" in fields:
        values.update(recurrence_values(update_data.recurrence))
    if not values and "tag_ids" not in fields and "commitment_ids" not in fields:
        raise DomainValidationError("empty_update", "At least one task field is required.")

    with transaction(session):
        task = repository.update(
            workspace.id,
            task_id,
            update_data.revision,
            values,
        )
        if update_data.tag_ids is not None:
            replace_tag_links(
                session,
                workspace.id,
                DomainEntityType.TASK,
                task.id,
                update_data.tag_ids,
            )
        if update_data.commitment_ids is not None:
            replace_commitment_links(
                session,
                workspace.id,
                CommitmentEntityType.TASK,
                task.id,
                update_data.commitment_ids,
            )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TASK,
            entity_id=task.id,
            action="task_updated",
            title=f"Task updated: {task.title}",
            payload={"fields": sorted(fields - {"revision"})},
        )
    return _task_responses(session, repository, [task])[0]


def delete_task(session: Session, task_id: UUID, revision: int) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    current = repository.get_active(workspace.id, task_id)
    if current is None:
        raise DomainNotFoundError("task", task_id)
    with transaction(session):
        dependencies = session.exec(
            select(TaskDependency).where(
                (col(TaskDependency.task_id) == task_id)
                | (col(TaskDependency.depends_on_task_id) == task_id)
            )
        ).all()
        for dependency in dependencies:
            session.delete(dependency)
        session.execute(
            update(Task)
            .where(col(Task.parent_task_id) == task_id, col(Task.deleted_at).is_(None))
            .values(parent_task_id=None)
        )
        for model in (NoteEntityLink, CalendarEventEntityLink):
            links = session.exec(
                select(model).where(
                    col(model.workspace_id) == workspace.id,
                    col(model.entity_type) == DomainEntityType.TASK,
                    col(model.entity_id) == task_id,
                )
            ).all()
            for link in links:
                session.delete(link)
        remove_generic_links(
            session,
            workspace.id,
            DomainEntityType.TASK,
            CommitmentEntityType.TASK,
            task_id,
        )
        task = repository.soft_delete(workspace.id, task_id, revision)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TASK,
            entity_id=task.id,
            action="task_deleted",
            title=f"Task deleted: {task.title}",
        )
    return DeletedResource(id=task_id)


def _would_create_dependency_cycle(
    edges: list[tuple[UUID, UUID]],
    task_id: UUID,
    depends_on_id: UUID,
) -> bool:
    adjacency: dict[UUID, set[UUID]] = {}
    for source, target in edges:
        adjacency.setdefault(source, set()).add(target)
    adjacency.setdefault(task_id, set()).add(depends_on_id)
    stack = [depends_on_id]
    visited: set[UUID] = set()
    while stack:
        current = stack.pop()
        if current == task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency.get(current, ()))
    return False


def add_task_dependency(
    session: Session,
    task_id: UUID,
    create_data: TaskDependencyRequest,
) -> TaskDependencyResponse:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    task = repository.get_active(workspace.id, task_id)
    prerequisite = repository.get_active(workspace.id, create_data.depends_on_task_id)
    if task is None:
        raise DomainNotFoundError("task", task_id)
    if prerequisite is None:
        raise DomainNotFoundError("task", create_data.depends_on_task_id)
    if task_id == prerequisite.id:
        raise DomainValidationError("task_dependency_self", "A task cannot depend on itself.")
    if _would_create_dependency_cycle(
        repository.graph_edges(workspace.id),
        task_id,
        prerequisite.id,
    ):
        raise DomainConflictError(
            "task_dependency_cycle",
            "This dependency would create a cycle.",
        )
    duplicate = session.exec(
        select(TaskDependency).where(
            col(TaskDependency.task_id) == task_id,
            col(TaskDependency.depends_on_task_id) == prerequisite.id,
            col(TaskDependency.dependency_type) == create_data.dependency_type,
        )
    ).first()
    if duplicate is not None:
        raise DomainConflictError(
            "duplicate_task_dependency",
            "This task dependency already exists.",
        )
    with transaction(session):
        dependency = repository.add_dependency(
            TaskDependency(
                workspace_id=workspace.id,
                task_id=task_id,
                **create_data.model_dump(),
            )
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TASK,
            entity_id=task.id,
            action="task_dependency_added",
            title=f"Dependency added to: {task.title}",
            payload={"depends_on_task_id": str(prerequisite.id)},
        )
    return TaskDependencyResponse.model_validate(dependency)


def remove_task_dependency(
    session: Session,
    task_id: UUID,
    dependency_id: UUID,
) -> DeletedResource:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    task = repository.get_active(workspace.id, task_id)
    if task is None:
        raise DomainNotFoundError("task", task_id)
    dependency = repository.get_dependency(workspace.id, task_id, dependency_id)
    if dependency is None:
        raise DomainNotFoundError("task_dependency", dependency_id)
    with transaction(session):
        session.delete(dependency)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.TASK,
            entity_id=task.id,
            action="task_dependency_removed",
            title=f"Dependency removed from: {task.title}",
        )
    return DeletedResource(id=dependency_id)


def bulk_complete_tasks(
    session: Session,
    request: BulkCompleteRequest,
) -> list[TaskResponse]:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    current: dict[UUID, Task] = {}
    for item in request.items:
        task = repository.get_active(workspace.id, item.id)
        if task is None:
            raise DomainNotFoundError("task", item.id)
        _validate_status_transition(task.status, TaskStatus.COMPLETED)
        current[item.id] = task
    completed: list[Task] = []
    completed_at = datetime.now(UTC)
    with transaction(session):
        for item in request.items:
            values: dict[str, object] = {
                "status": TaskStatus.COMPLETED,
                "completed_at": completed_at,
            }
            if item.actual_duration_minutes is not None:
                values["actual_duration_minutes"] = item.actual_duration_minutes
            task = repository.update(workspace.id, item.id, item.revision, values)
            completed.append(task)
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TASK,
                entity_id=task.id,
                action="task_completed",
                title=f"Task completed: {task.title}",
            )
    return _task_responses(session, repository, completed)


def bulk_reschedule_tasks(
    session: Session,
    request: BulkRescheduleRequest,
) -> list[TaskResponse]:
    workspace = get_current_workspace(session)
    repository = TaskRepository(session)
    for item in request.items:
        if repository.get_active(workspace.id, item.id) is None:
            raise DomainNotFoundError("task", item.id)
    rescheduled: list[Task] = []
    with transaction(session):
        for item in request.items:
            task = repository.update(
                workspace.id,
                item.id,
                item.revision,
                {
                    "scheduled_start_at": item.scheduled_start_at,
                    "scheduled_end_at": item.scheduled_end_at,
                },
            )
            rescheduled.append(task)
            emit_timeline_event(
                session,
                workspace_id=workspace.id,
                entity_type=DomainEntityType.TASK,
                entity_id=task.id,
                action="task_rescheduled",
                title=f"Task rescheduled: {task.title}",
            )
    return _task_responses(session, repository, rescheduled)


def expand_task_occurrences(
    session: Session,
    task_id: UUID,
    range_start: datetime,
    range_end: datetime,
) -> list[RecurrenceOccurrenceResponse]:
    workspace = get_current_workspace(session)
    task = TaskRepository(session).get_active(workspace.id, task_id)
    if task is None:
        raise DomainNotFoundError("task", task_id)
    if task.recurrence_rrule is None:
        return []
    dtstart = task.scheduled_start_at or task.due_at
    if dtstart is None:
        raise DomainValidationError(
            "recurrence_start_missing",
            "A recurring task requires a due date or scheduled start.",
        )
    duration = (
        task.scheduled_end_at - task.scheduled_start_at
        if task.scheduled_start_at is not None and task.scheduled_end_at is not None
        else timedelta(minutes=task.estimated_duration_minutes)
        if task.estimated_duration_minutes is not None
        else None
    )
    try:
        occurrences = expand_recurrence(
            task.recurrence_rrule,
            dtstart=dtstart,
            range_start=range_start,
            range_end=range_end,
        )
    except ValueError as exc:
        raise DomainValidationError("invalid_recurrence", str(exc)) from exc
    return [
        RecurrenceOccurrenceResponse(
            starts_at=occurrence,
            ends_at=occurrence + duration if duration is not None else None,
        )
        for occurrence in occurrences
    ]
