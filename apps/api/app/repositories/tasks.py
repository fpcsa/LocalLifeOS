from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import and_, asc, desc, exists, func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models import (
    CommitmentEntityLink,
    CommitmentEntityType,
    DomainEntityType,
    TagEntityLink,
    Task,
    TaskDependency,
    TaskDependencyType,
    TaskPriority,
    TaskStatus,
)
from app.repositories.base import PageResult
from app.repositories.revisioned import RevisionedRepository

TaskSort = Literal["created_at", "updated_at", "due_at", "priority", "title"]


class TaskRepository(RevisionedRepository[Task]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Task, "task")

    def list_page(
        self,
        workspace_id: UUID,
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
        now: datetime,
        sort: TaskSort,
        descending: bool,
    ) -> PageResult[Task]:
        filters: list[ColumnElement[bool]] = [
            col(Task.workspace_id) == workspace_id,
            col(Task.deleted_at).is_(None),
        ]
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    col(Task.title).ilike(pattern),
                    col(Task.description_markdown).ilike(pattern),
                )
            )
        if project_id is not None:
            filters.append(col(Task.project_id) == project_id)
        if parent_task_id is not None:
            filters.append(col(Task.parent_task_id) == parent_task_id)
        if status is not None:
            filters.append(col(Task.status) == status)
        if priority is not None:
            filters.append(col(Task.priority) == priority)
        if tag_id is not None:
            filters.append(
                exists(
                    select(TagEntityLink.id).where(
                        col(TagEntityLink.workspace_id) == workspace_id,
                        col(TagEntityLink.tag_id) == tag_id,
                        col(TagEntityLink.entity_type) == DomainEntityType.TASK,
                        col(TagEntityLink.entity_id) == col(Task.id),
                    )
                )
            )
        if due_before is not None:
            filters.append(col(Task.due_at) <= due_before)
        if due_after is not None:
            filters.append(col(Task.due_at) >= due_after)

        overdue_expression = and_(
            col(Task.due_at).is_not(None),
            col(Task.due_at) < now,
            col(Task.status).not_in((TaskStatus.COMPLETED, TaskStatus.CANCELLED)),
        )
        dependency = aliased(Task)
        blocked_expression = exists(
            select(TaskDependency.id)
            .join(dependency, col(TaskDependency.depends_on_task_id) == dependency.id)
            .where(
                col(TaskDependency.workspace_id) == workspace_id,
                col(TaskDependency.task_id) == col(Task.id),
                cast(Any, dependency.deleted_at).is_(None),
                or_(
                    and_(
                        col(TaskDependency.dependency_type) == TaskDependencyType.FINISH_TO_START,
                        cast(Any, dependency.status) != TaskStatus.COMPLETED,
                    ),
                    and_(
                        col(TaskDependency.dependency_type) == TaskDependencyType.START_TO_START,
                        cast(Any, dependency.status) == TaskStatus.TODO,
                    ),
                ),
            )
        )
        schedulable_expression = and_(
            col(Task.status).not_in((TaskStatus.COMPLETED, TaskStatus.CANCELLED)),
            col(Task.estimated_duration_minutes).is_not(None),
            col(Task.scheduled_start_at).is_(None),
            ~blocked_expression,
        )
        for requested, expression in (
            (overdue, overdue_expression),
            (blocked, blocked_expression),
            (schedulable, schedulable_expression),
        ):
            if requested is not None:
                filters.append(expression if requested else ~expression)

        total = self.session.exec(select(func.count()).select_from(Task).where(*filters)).one()
        sort_column = cast(
            ColumnElement[Any],
            {
                "created_at": col(Task.created_at),
                "updated_at": col(Task.updated_at),
                "due_at": col(Task.due_at),
                "priority": col(Task.priority),
                "title": func.lower(col(Task.title)),
            }[sort],
        )
        order = desc(sort_column) if descending else asc(sort_column)
        items = list(
            self.session.exec(
                select(Task)
                .where(*filters)
                .order_by(order, col(Task.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def dependencies_for(self, task_ids: list[UUID]) -> dict[UUID, list[TaskDependency]]:
        result: dict[UUID, list[TaskDependency]] = {task_id: [] for task_id in task_ids}
        if not task_ids:
            return result
        dependencies = self.session.exec(
            select(TaskDependency)
            .where(col(TaskDependency.task_id).in_(task_ids))
            .order_by(col(TaskDependency.created_at), col(TaskDependency.id))
        ).all()
        for dependency in dependencies:
            result.setdefault(dependency.task_id, []).append(dependency)
        return result

    def tag_ids_for(self, task_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {task_id: [] for task_id in task_ids}
        if not task_ids:
            return result
        rows = self.session.exec(
            select(TagEntityLink.entity_id, TagEntityLink.tag_id).where(
                col(TagEntityLink.entity_type) == DomainEntityType.TASK,
                col(TagEntityLink.entity_id).in_(task_ids),
            )
        ).all()
        for task_id, tag_id in rows:
            result.setdefault(task_id, []).append(tag_id)
        return result

    def commitment_ids_for(self, task_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {task_id: [] for task_id in task_ids}
        if not task_ids:
            return result
        rows = self.session.exec(
            select(
                CommitmentEntityLink.entity_id,
                CommitmentEntityLink.commitment_id,
            ).where(
                col(CommitmentEntityLink.entity_type) == CommitmentEntityType.TASK,
                col(CommitmentEntityLink.entity_id).in_(task_ids),
            )
        ).all()
        for task_id, commitment_id in rows:
            result.setdefault(task_id, []).append(commitment_id)
        return result

    def child_counts(self, task_ids: list[UUID]) -> dict[UUID, int]:
        if not task_ids:
            return {}
        rows = self.session.exec(
            select(col(Task.parent_task_id), func.count(col(Task.id)))
            .where(
                col(Task.parent_task_id).in_(task_ids),
                col(Task.deleted_at).is_(None),
            )
            .group_by(col(Task.parent_task_id))
        ).all()
        return {parent_id: int(count) for parent_id, count in rows if parent_id is not None}

    def add_dependency(self, dependency: TaskDependency) -> TaskDependency:
        self.session.add(dependency)
        self.session.flush()
        self.session.refresh(dependency)
        return dependency

    def get_dependency(
        self,
        workspace_id: UUID,
        task_id: UUID,
        dependency_id: UUID,
    ) -> TaskDependency | None:
        return self.session.exec(
            select(TaskDependency).where(
                col(TaskDependency.id) == dependency_id,
                col(TaskDependency.workspace_id) == workspace_id,
                col(TaskDependency.task_id) == task_id,
            )
        ).first()

    def graph_edges(self, workspace_id: UUID) -> list[tuple[UUID, UUID]]:
        return list(
            self.session.exec(
                select(TaskDependency.task_id, TaskDependency.depends_on_task_id).where(
                    col(TaskDependency.workspace_id) == workspace_id
                )
            ).all()
        )
