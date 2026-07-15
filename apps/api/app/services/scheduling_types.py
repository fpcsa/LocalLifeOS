from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.models import (
    CalendarEvent,
    Commitment,
    PreferredTimeOfDay,
    Task,
    TaskDependency,
)


@dataclass(frozen=True)
class TimeInterval:
    starts_at: datetime
    ends_at: datetime

    @property
    def duration_minutes(self) -> int:
        return max(0, int((self.ends_at - self.starts_at).total_seconds() // 60))


@dataclass(frozen=True)
class BusyInterval(TimeInterval):
    kind: str
    entity_id: UUID
    title: str
    event: CalendarEvent | None = None
    task: Task | None = None


@dataclass(frozen=True)
class TaskSchedulingInput:
    task: Task
    duration_minutes: int | None
    earliest_start_at: datetime
    deadline_at: datetime
    preferred_time_of_day: PreferredTimeOfDay
    dependencies: tuple[TaskDependency, ...] = ()


@dataclass
class SchedulingEvidence:
    workspace_id: UUID
    timezone_name: str
    week_starts_on: int
    selected_tasks: list[Task]
    dependencies: dict[UUID, list[TaskDependency]]
    dependency_targets: dict[UUID, Task | None]
    existing_scheduled_tasks: list[Task]
    calendar_busy: list[BusyInterval]
    task_busy: list[BusyInterval]
    commitment: Commitment | None
    source_snapshot: dict[str, object]
    source_fingerprint: str

    @property
    def all_busy(self) -> list[BusyInterval]:
        return [*self.calendar_busy, *self.task_busy]


@dataclass(frozen=True)
class SolverWindow:
    starts_minute: int
    latest_start_minute: int
    ends_minute: int
    local_date_ordinal: int
    preference_starts_minute: int | None
    preference_ends_minute: int | None

    @property
    def duration_minutes(self) -> int:
        return self.ends_minute - self.starts_minute


@dataclass(frozen=True)
class SolverTask:
    source: TaskSchedulingInput
    windows: tuple[SolverWindow, ...]
    precluded_reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolverPlacement:
    task_id: UUID
    starts_minute: int
    ends_minute: int
    selected_window: SolverWindow
    preference_satisfied: bool


@dataclass
class RawSolverResult:
    status: str
    optimality_proven: bool
    solve_duration_ms: int
    placements: list[SolverPlacement] = field(default_factory=list)
    selected_task_ids: set[UUID] = field(default_factory=set)
    objective_value: float | None = None
    best_bound: float | None = None
