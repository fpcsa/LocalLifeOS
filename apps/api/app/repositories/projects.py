from __future__ import annotations

from datetime import date
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import asc, case, desc, func
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models import Project, ProjectStatus, Task, TaskStatus
from app.repositories.base import PageResult
from app.repositories.revisioned import RevisionedRepository

ProjectSort = Literal["name", "created_at", "updated_at", "target_end_date"]


class ProjectRepository(RevisionedRepository[Project]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Project, "project")

    def list_page(
        self,
        workspace_id: UUID,
        *,
        page: int,
        page_size: int,
        query: str | None,
        status: ProjectStatus | None,
        target_before: date | None,
        sort: ProjectSort,
        descending: bool,
    ) -> PageResult[Project]:
        filters: list[ColumnElement[bool]] = [
            col(Project.workspace_id) == workspace_id,
            col(Project.deleted_at).is_(None),
        ]
        if query:
            filters.append(col(Project.name).ilike(f"%{query.strip()}%"))
        if status is not None:
            filters.append(col(Project.status) == status)
        if target_before is not None:
            filters.append(col(Project.target_end_date) <= target_before)

        total = self.session.exec(select(func.count()).select_from(Project).where(*filters)).one()
        sort_column = cast(
            ColumnElement[Any],
            {
                "name": func.lower(col(Project.name)),
                "created_at": col(Project.created_at),
                "updated_at": col(Project.updated_at),
                "target_end_date": col(Project.target_end_date),
            }[sort],
        )
        order = desc(sort_column) if descending else asc(sort_column)
        items = list(
            self.session.exec(
                select(Project)
                .where(*filters)
                .order_by(order, col(Project.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PageResult(items=items, total=total)

    def progress_for(
        self, workspace_id: UUID, project_ids: list[UUID]
    ) -> dict[UUID, tuple[int, int]]:
        if not project_ids:
            return {}
        rows = self.session.exec(
            select(
                col(Task.project_id),
                func.count(col(Task.id)),
                func.sum(case((col(Task.status) == TaskStatus.COMPLETED, 1), else_=0)),
            )
            .where(
                col(Task.workspace_id) == workspace_id,
                col(Task.project_id).in_(project_ids),
                col(Task.deleted_at).is_(None),
                col(Task.status) != TaskStatus.CANCELLED,
            )
            .group_by(col(Task.project_id))
        ).all()
        return {
            project_id: (int(total), int(completed or 0))
            for project_id, total, completed in rows
            if project_id is not None
        }
