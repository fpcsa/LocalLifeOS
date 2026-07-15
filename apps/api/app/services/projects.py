from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlmodel import Session

from app.core.exceptions import DomainNotFoundError, DomainValidationError
from app.db.transactions import transaction
from app.models import DomainEntityType, Project, ProjectStatus
from app.repositories.projects import ProjectRepository, ProjectSort
from app.schemas.common import SortOrder
from app.schemas.productivity import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.events import emit_timeline_event
from app.services.workspace import get_current_workspace


def _project_responses(
    repository: ProjectRepository,
    workspace_id: UUID,
    projects: list[Project],
) -> list[ProjectResponse]:
    progress = repository.progress_for(workspace_id, [project.id for project in projects])
    responses: list[ProjectResponse] = []
    for project in projects:
        total, completed = progress.get(project.id, (0, 0))
        basis_points = round(completed * 10_000 / total) if total else 0
        responses.append(
            ProjectResponse(
                **project.model_dump(exclude={"deleted_at"}),
                total_tasks=total,
                completed_tasks=completed,
                progress_basis_points=basis_points,
            )
        )
    return responses


def list_projects(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    status: ProjectStatus | None,
    target_before: date | None,
    sort: ProjectSort,
    order: SortOrder,
) -> tuple[list[ProjectResponse], int]:
    workspace = get_current_workspace(session)
    repository = ProjectRepository(session)
    result = repository.list_page(
        workspace.id,
        page=page,
        page_size=page_size,
        query=query,
        status=status,
        target_before=target_before,
        sort=sort,
        descending=order == SortOrder.DESC,
    )
    return _project_responses(repository, workspace.id, result.items), result.total


def get_project(session: Session, project_id: UUID) -> ProjectResponse:
    workspace = get_current_workspace(session)
    repository = ProjectRepository(session)
    project = repository.get_active(workspace.id, project_id)
    if project is None:
        raise DomainNotFoundError("project", project_id)
    return _project_responses(repository, workspace.id, [project])[0]


def create_project(session: Session, create_data: ProjectCreateRequest) -> ProjectResponse:
    workspace = get_current_workspace(session)
    repository = ProjectRepository(session)
    with transaction(session):
        project = repository.add(Project(workspace_id=workspace.id, **create_data.model_dump()))
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.PROJECT,
            entity_id=project.id,
            action="project_created",
            title=f"Project created: {project.name}",
        )
    return _project_responses(repository, workspace.id, [project])[0]


def update_project(
    session: Session,
    project_id: UUID,
    update_data: ProjectUpdateRequest,
) -> ProjectResponse:
    workspace = get_current_workspace(session)
    repository = ProjectRepository(session)
    current = repository.get_active(workspace.id, project_id)
    if current is None:
        raise DomainNotFoundError("project", project_id)
    values = update_data.model_dump(exclude={"revision"}, exclude_unset=True)
    if not values:
        raise DomainValidationError("empty_update", "At least one project field is required.")
    start = values.get("target_start_date", current.target_start_date)
    end = values.get("target_end_date", current.target_end_date)
    if start is not None and end is not None and end < start:
        raise DomainValidationError(
            "invalid_project_target_range",
            "target_end_date cannot be before target_start_date.",
        )
    if current.status == ProjectStatus.ARCHIVED and values.get("status") != ProjectStatus.ARCHIVED:
        raise DomainValidationError(
            "archived_project",
            "Archived projects cannot be edited or reopened.",
        )
    with transaction(session):
        project = repository.update(workspace.id, project_id, update_data.revision, values)
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.PROJECT,
            entity_id=project.id,
            action="project_updated",
            title=f"Project updated: {project.name}",
            payload={"fields": sorted(values)},
        )
    return _project_responses(repository, workspace.id, [project])[0]


def archive_project(session: Session, project_id: UUID, revision: int) -> ProjectResponse:
    workspace = get_current_workspace(session)
    repository = ProjectRepository(session)
    current = repository.get_active(workspace.id, project_id)
    if current is None:
        raise DomainNotFoundError("project", project_id)
    with transaction(session):
        project = repository.update(
            workspace.id,
            project_id,
            revision,
            {"status": ProjectStatus.ARCHIVED},
        )
        emit_timeline_event(
            session,
            workspace_id=workspace.id,
            entity_type=DomainEntityType.PROJECT,
            entity_id=project.id,
            action="project_archived",
            title=f"Project archived: {project.name}",
        )
    return _project_responses(repository, workspace.id, [project])[0]
