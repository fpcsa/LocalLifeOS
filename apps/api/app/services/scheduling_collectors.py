from __future__ import annotations

import hashlib
import json
from datetime import UTC
from uuid import UUID

from sqlmodel import Session, col, select

from app.core.exceptions import DomainConflictError, DomainNotFoundError, DomainValidationError
from app.models import (
    CommitmentEntityType,
    CommitmentStatus,
    Task,
    TaskStatus,
)
from app.repositories.commitments import CommitmentRepository
from app.repositories.tasks import TaskRepository
from app.schemas.scheduling import SchedulingScopeInput
from app.services.calendar import calendar_occurrences_in_range
from app.services.scheduling_types import BusyInterval, SchedulingEvidence
from app.services.workspace import get_current_workspace, get_preferences


def _task_snapshot(task: Task) -> dict[str, object]:
    return {
        "id": str(task.id),
        "revision": task.revision,
        "status": task.status.value,
        "duration": task.estimated_duration_minutes,
        "earliest": task.earliest_start_at.astimezone(UTC).isoformat()
        if task.earliest_start_at
        else None,
        "due": task.due_at.astimezone(UTC).isoformat() if task.due_at else None,
        "scheduled_start": task.scheduled_start_at.astimezone(UTC).isoformat()
        if task.scheduled_start_at
        else None,
        "scheduled_end": task.scheduled_end_at.astimezone(UTC).isoformat()
        if task.scheduled_end_at
        else None,
        "priority": task.priority.value,
        "preferred_time": task.preferred_time_of_day.value,
    }


def _fingerprint(snapshot: dict[str, object]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _target_revision(target: Task | None) -> int | None:
    return target.revision if target is not None else None


def collect_scheduling_evidence(
    session: Session,
    request: SchedulingScopeInput,
    *,
    task_ids: list[UUID],
    commitment_id: UUID | None,
) -> SchedulingEvidence:
    workspace = get_current_workspace(session)
    preferences = get_preferences(session)
    task_repository = TaskRepository(session)
    selected_tasks: list[Task] = []
    for task_id in task_ids:
        task = task_repository.get_active(workspace.id, task_id)
        if task is None:
            raise DomainNotFoundError("task", task_id)
        selected_tasks.append(task)

    commitment = None
    if commitment_id is not None:
        commitment_repository = CommitmentRepository(session)
        commitment = commitment_repository.get_active(workspace.id, commitment_id)
        if commitment is None:
            raise DomainNotFoundError("commitment", commitment_id)
        if commitment.status in {
            CommitmentStatus.CANCELLED,
            CommitmentStatus.COMPLETED,
            CommitmentStatus.ARCHIVED,
        }:
            raise DomainConflictError(
                "commitment_not_schedulable",
                "Completed, cancelled, or archived commitments cannot be scheduled.",
            )
        linked_task_ids = {
            link.entity_id
            for link in commitment_repository.links_for([commitment.id]).get(commitment.id, [])
            if link.entity_type == CommitmentEntityType.TASK
        }
        unlinked = sorted(set(task_ids) - linked_task_ids, key=str)
        if unlinked:
            raise DomainValidationError(
                "commitment_task_mismatch",
                "Every requested task must be linked to the commitment.",
                {"task_ids": [str(item) for item in unlinked]},
            )

    dependencies = task_repository.dependencies_for(task_ids)
    dependency_targets: dict[UUID, Task | None] = {}
    for task_dependencies in dependencies.values():
        for dependency in task_dependencies:
            target = task_repository.get_active(workspace.id, dependency.depends_on_task_id)
            dependency_targets[dependency.id] = target

    existing_scheduled_tasks = list(
        session.exec(
            select(Task)
            .where(
                col(Task.workspace_id) == workspace.id,
                col(Task.deleted_at).is_(None),
                col(Task.status) != TaskStatus.CANCELLED,
                col(Task.scheduled_start_at).is_not(None),
                col(Task.scheduled_end_at).is_not(None),
                col(Task.scheduled_start_at) < request.planning_end_at,
                col(Task.scheduled_end_at) > request.planning_start_at,
            )
            .order_by(col(Task.scheduled_start_at), col(Task.id))
        ).all()
    )
    task_busy = [
        BusyInterval(
            starts_at=task.scheduled_start_at,
            ends_at=task.scheduled_end_at,
            kind="existing_task",
            entity_id=task.id,
            title=task.title,
            task=task,
        )
        for task in existing_scheduled_tasks
        if task.scheduled_start_at is not None and task.scheduled_end_at is not None
    ]
    occurrences = calendar_occurrences_in_range(
        session,
        range_start=request.planning_start_at,
        range_end=request.planning_end_at,
    )
    calendar_busy = [
        BusyInterval(
            starts_at=item.effective_starts_at,
            ends_at=item.effective_ends_at,
            kind="calendar_event",
            entity_id=item.event.id,
            title=item.event.title,
            event=item.event,
        )
        for item in occurrences
    ]

    selected_snapshot = [_task_snapshot(task) for task in selected_tasks]
    scheduled_snapshot = [_task_snapshot(task) for task in existing_scheduled_tasks]
    dependency_snapshot = [
        {
            "id": str(dependency.id),
            "task_id": str(dependency.task_id),
            "depends_on_task_id": str(dependency.depends_on_task_id),
            "type": dependency.dependency_type.value,
            "created_at": dependency.created_at.astimezone(UTC).isoformat(),
            "target_revision": _target_revision(dependency_targets[dependency.id]),
        }
        for task_id in task_ids
        for dependency in dependencies.get(task_id, [])
    ]
    event_snapshot = [
        {
            "id": str(event.id),
            "revision": event.revision,
        }
        for event in sorted(
            {item.event.id: item.event for item in occurrences}.values(),
            key=lambda item: str(item.id),
        )
    ]
    source_snapshot: dict[str, object] = {
        "workspace_id": str(workspace.id),
        "preferences": {
            "id": str(preferences.id),
            "revision": preferences.revision,
            "timezone": preferences.timezone,
            "week_starts_on": preferences.week_starts_on,
        },
        "selected_tasks": selected_snapshot,
        "scheduled_tasks": scheduled_snapshot,
        "dependencies": dependency_snapshot,
        "events": event_snapshot,
        "commitment": {
            "id": str(commitment.id),
            "revision": commitment.revision,
            "target_end": commitment.ends_at.astimezone(UTC).isoformat()
            if commitment.ends_at
            else None,
        }
        if commitment is not None
        else None,
    }
    return SchedulingEvidence(
        workspace_id=workspace.id,
        timezone_name=preferences.timezone,
        week_starts_on=preferences.week_starts_on,
        selected_tasks=selected_tasks,
        dependencies=dependencies,
        dependency_targets=dependency_targets,
        existing_scheduled_tasks=existing_scheduled_tasks,
        calendar_busy=calendar_busy,
        task_busy=task_busy,
        commitment=commitment,
        source_snapshot=source_snapshot,
        source_fingerprint=_fingerprint(source_snapshot),
    )
