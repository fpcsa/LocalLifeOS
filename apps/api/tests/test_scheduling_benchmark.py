from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter

from sqlmodel import Session

from app.models import CalendarEvent, Task, TaskPriority
from app.schemas.scheduling import SchedulingPreviewRequest
from app.services.scheduling import create_scheduling_preview
from app.services.workspace import get_current_workspace


def test_bounded_maximum_scheduling_fixture_completes_within_solver_limit(
    db_session: Session,
) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "scheduling_benchmarks.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    limits = fixture["limits"]
    scenario = fixture["scenarios"][-1]
    assert scenario == {
        "name": "bounded_maximum",
        "task_count": limits["maximum_tasks"],
        "event_count": limits["maximum_events"],
        "horizon_days": limits["maximum_horizon_days"],
        "solver_time_limit_seconds": 1.0,
    }

    workspace = get_current_workspace(db_session)
    horizon_start = datetime(2026, 8, 3, tzinfo=UTC)
    horizon_end = horizon_start + timedelta(days=scenario["horizon_days"])
    priorities = list(TaskPriority)
    tasks = [
        Task(
            workspace_id=workspace.id,
            title=f"Benchmark task {index:03d}",
            priority=priorities[index % len(priorities)],
            estimated_duration_minutes=30 + (index % 3) * 15,
            earliest_start_at=horizon_start,
            due_at=horizon_end,
        )
        for index in range(scenario["task_count"])
    ]
    events: list[CalendarEvent] = []
    for index in range(scenario["event_count"]):
        day_offset = index // 8
        slot = index % 8
        starts_at = horizon_start + timedelta(
            days=day_offset,
            hours=9,
            minutes=slot * 45,
        )
        events.append(
            CalendarEvent(
                workspace_id=workspace.id,
                title=f"Benchmark calendar constraint {index:03d}",
                starts_at=starts_at,
                ends_at=starts_at + timedelta(minutes=15),
                timezone="UTC",
            )
        )
    db_session.add_all([*tasks, *events])
    db_session.commit()

    request = SchedulingPreviewRequest(
        planning_start_at=horizon_start,
        planning_end_at=horizon_end,
        task_ids=[task.id for task in tasks],
        solver_time_limit_seconds=scenario["solver_time_limit_seconds"],
    )
    started = perf_counter()
    preview = create_scheduling_preview(db_session, request)
    elapsed_seconds = perf_counter() - started

    accounted_task_ids = {item.task_id for item in preview.placements} | {
        item.task_id for item in preview.unscheduled_tasks
    }
    assert accounted_task_ids == {task.id for task in tasks}
    assert preview.solve_duration_ms <= 1_500
    assert elapsed_seconds < 30
