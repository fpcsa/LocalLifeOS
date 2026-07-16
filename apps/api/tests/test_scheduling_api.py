from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from app.repositories import TaskRepository
from fastapi.testclient import TestClient
from ortools.sat.python import cp_model


def _data(response: Any, expected_status: int = 200) -> Any:
    assert response.status_code == expected_status, response.text
    return response.json()["data"]


def _task(client: TestClient, title: str, **values: object) -> dict[str, Any]:
    return _data(
        client.post("/api/v1/tasks", json={"title": title, **values}),
        201,
    )


def _event(client: TestClient, title: str, **values: object) -> dict[str, Any]:
    return _data(
        client.post(
            "/api/v1/calendar/events",
            json={"title": title, "timezone": "UTC", **values},
        ),
        201,
    )


def _scope(
    start: str = "2026-07-20T09:00:00Z",
    end: str = "2026-07-20T17:00:00Z",
    **values: object,
) -> dict[str, object]:
    return {
        "planning_start_at": start,
        "planning_end_at": end,
        **values,
    }


def _preview(
    client: TestClient,
    task_ids: list[str],
    **scope: object,
) -> dict[str, Any]:
    return _data(
        client.post(
            "/api/v1/scheduling/preview",
            json={"task_ids": task_ids, **_scope(**scope)},
        ),
        201,
    )


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_preview_orders_dependencies_avoids_buffers_and_applies_atomically(
    client: TestClient,
) -> None:
    prerequisite = _task(
        client,
        "Prepare briefing",
        estimated_duration_minutes=60,
        earliest_start_at="2026-07-20T09:00:00Z",
        due_at="2026-07-20T16:00:00Z",
        priority="urgent",
    )
    dependent = _task(
        client,
        "Deliver briefing",
        estimated_duration_minutes=45,
        due_at="2026-07-20T17:00:00Z",
        priority="high",
    )
    _data(
        client.post(
            f"/api/v1/tasks/{dependent['id']}/dependencies",
            json={"depends_on_task_id": prerequisite["id"]},
        ),
        201,
    )
    _event(
        client,
        "Client call",
        starts_at="2026-07-20T11:00:00Z",
        ends_at="2026-07-20T12:00:00Z",
        preparation_buffer_minutes=15,
        recovery_buffer_minutes=15,
        recurrence={"rrule": "FREQ=DAILY;COUNT=2"},
    )

    preview = _preview(client, [prerequisite["id"], dependent["id"]])
    assert preview["solver_status"] in {"optimal", "feasible"}
    assert preview["optimality_proven"] is (preview["solver_status"] == "optimal")
    assert len(preview["placements"]) == 2
    assert preview["unscheduled_tasks"] == []

    placements = {item["task_id"]: item for item in preview["placements"]}
    first = placements[prerequisite["id"]]
    second = placements[dependent["id"]]
    assert _as_datetime(first["ends_at"]) <= _as_datetime(second["starts_at"])
    hard_start = _as_datetime("2026-07-20T10:45:00Z")
    hard_end = _as_datetime("2026-07-20T12:15:00Z")
    for placement in placements.values():
        start = _as_datetime(placement["starts_at"])
        end = _as_datetime(placement["ends_at"])
        assert end <= hard_start or start >= hard_end

    # A preview is persisted for explanation and staleness checks, but is non-mutating.
    for task in (prerequisite, dependent):
        current = _data(client.get(f"/api/v1/tasks/{task['id']}"))
        assert current["scheduled_start_at"] is None
        assert current["revision"] == task["revision"]
    explanation = _data(client.get(f"/api/v1/scheduling/explanations/{preview['preview_id']}"))
    assert explanation["solver_status"] == preview["solver_status"]
    assert any(item["kind"] == "calendar_event" for item in explanation["conflicts"])

    applied = _data(
        client.post(
            "/api/v1/scheduling/apply",
            json={"preview_id": preview["preview_id"]},
        )
    )
    assert {item["task_id"] for item in applied["placements"]} == {
        prerequisite["id"],
        dependent["id"],
    }
    for task_id, placement in placements.items():
        current = _data(client.get(f"/api/v1/tasks/{task_id}"))
        assert current["scheduled_start_at"] == placement["starts_at"]
        assert current["scheduled_end_at"] == placement["ends_at"]
        assert current["revision"] == placement["expected_revision"] + 1

    timeline = client.get(
        "/api/v1/timeline",
        params={"action": "task_schedule_applied", "page_size": 10},
    )
    assert timeline.status_code == 200
    assert timeline.json()["meta"]["total_items"] == 2
    repeated = client.post(
        "/api/v1/scheduling/apply",
        json={"preview_id": preview["preview_id"]},
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "scheduling_preview_already_applied"


def test_insufficient_capacity_reports_all_day_hard_constraint(client: TestClient) -> None:
    task = _task(
        client,
        "Deep work",
        estimated_duration_minutes=120,
        due_at="2026-07-20T17:00:00Z",
    )
    event = _event(
        client,
        "Company holiday",
        all_day=True,
        all_day_start="2026-07-20",
        all_day_end="2026-07-21",
    )

    preview = _preview(client, [task["id"]])
    assert preview["placements"] == []
    assert len(preview["unscheduled_tasks"]) == 1
    reason_codes = {reason["code"] for reason in preview["unscheduled_tasks"][0]["reasons"]}
    assert "hard_calendar_conflict" in reason_codes
    assert "insufficient_contiguous_capacity" in reason_codes
    assert preview["capacity"]["available_focus_minutes"] == 0
    conflict = next(item for item in preview["conflicts"] if item["kind"] == "calendar_event")
    assert conflict["hard"] is True
    assert conflict["entity"]["entity_id"] == event["id"]


def test_competing_priorities_respect_existing_scheduled_tasks(client: TestClient) -> None:
    existing = _task(
        client,
        "Existing manual block",
        estimated_duration_minutes=60,
        scheduled_start_at="2026-07-20T09:00:00Z",
        scheduled_end_at="2026-07-20T10:00:00Z",
    )
    low = _task(
        client,
        "Low-priority option",
        estimated_duration_minutes=60,
        due_at="2026-07-20T11:00:00Z",
        priority="low",
    )
    urgent = _task(
        client,
        "Urgent option",
        estimated_duration_minutes=60,
        due_at="2026-07-20T11:00:00Z",
        priority="urgent",
    )

    preview = _preview(
        client,
        [low["id"], urgent["id"]],
        end="2026-07-20T11:00:00Z",
    )
    assert [item["task_id"] for item in preview["placements"]] == [urgent["id"]]
    assert [item["task_id"] for item in preview["unscheduled_tasks"]] == [low["id"]]
    existing_conflict = next(
        item for item in preview["conflicts"] if item["kind"] == "existing_task"
    )
    assert existing_conflict["entity"]["entity_id"] == existing["id"]
    low_risk = next(item for item in preview["deadline_risks"] if item["task_id"] == low["id"])
    assert low_risk["level"] == "unscheduled"


def test_soft_preferences_cross_midnight_and_capacity_endpoint(client: TestClient) -> None:
    afternoon_only = _task(
        client,
        "Morning-preferred task",
        estimated_duration_minutes=60,
        preferred_time_of_day="morning",
        due_at="2026-07-20T15:00:00Z",
    )
    soft_preview = _preview(
        client,
        [afternoon_only["id"]],
        policy={
            "working_hours": [],
            "personal_availability_windows": [
                {
                    "starts_at": "2026-07-20T13:00:00Z",
                    "ends_at": "2026-07-20T15:00:00Z",
                }
            ],
        },
    )
    assert len(soft_preview["placements"]) == 1
    assert soft_preview["placements"][0]["preference_satisfied"] is False
    assert any(
        item["kind"] == "soft_preference" and item["hard"] is False
        for item in soft_preview["conflicts"]
    )

    overnight = _task(
        client,
        "Overnight maintenance",
        estimated_duration_minutes=120,
        earliest_start_at="2026-07-20T23:00:00Z",
        due_at="2026-07-21T02:00:00Z",
    )
    overnight_preview = _preview(
        client,
        [overnight["id"]],
        start="2026-07-20T20:00:00Z",
        end="2026-07-21T03:00:00Z",
        policy={
            "working_hours": [
                {
                    "weekday": 0,
                    "start_time": "22:00:00",
                    "end_time": "02:00:00",
                }
            ]
        },
    )
    placement = overnight_preview["placements"][0]
    assert _as_datetime(placement["starts_at"]).date() == datetime(2026, 7, 20).date()
    assert _as_datetime(placement["ends_at"]).date() == datetime(2026, 7, 21).date()
    monday = next(
        item for item in overnight_preview["capacity"]["days"] if item["local_date"] == "2026-07-20"
    )
    assert monday["suggested_task_minutes"] == 120

    capacity = _data(
        client.get(
            "/api/v1/scheduling/capacity",
            params={
                "start": "2026-07-20T09:00:00Z",
                "end": "2026-07-20T17:00:00Z",
                "minimum_focus_block_minutes": 45,
            },
        )
    )
    assert capacity["timezone"] == "UTC"
    assert capacity["required_task_minutes"] >= 180


def test_dst_transition_uses_real_elapsed_minutes(client: TestClient) -> None:
    preferences = _data(client.get("/api/v1/preferences"))
    _data(
        client.patch(
            "/api/v1/preferences",
            json={"revision": preferences["revision"], "timezone": "Europe/Rome"},
        )
    )
    task = _task(
        client,
        "DST maintenance",
        estimated_duration_minutes=180,
        earliest_start_at="2026-03-29T01:00:00+01:00",
        due_at="2026-03-29T05:00:00+02:00",
    )
    preview = _preview(
        client,
        [task["id"]],
        start="2026-03-28T23:00:00Z",
        end="2026-03-29T04:00:00Z",
        policy={
            "working_hours": [
                {
                    "weekday": 6,
                    "start_time": "01:00:00",
                    "end_time": "05:00:00",
                }
            ]
        },
    )
    assert preview["timezone"] == "Europe/Rome"
    assert len(preview["placements"]) == 1
    placement = preview["placements"][0]
    elapsed = _as_datetime(placement["ends_at"]) - _as_datetime(placement["starts_at"])
    assert elapsed.total_seconds() == 180 * 60
    assert preview["capacity"]["available_focus_minutes"] == 180

    repeated_hour_task = _task(
        client,
        "Repeated-hour maintenance",
        estimated_duration_minutes=120,
        earliest_start_at="2026-10-25T02:00:00+02:00",
        due_at="2026-10-25T03:00:00+01:00",
    )
    repeated_hour_preview = _preview(
        client,
        [repeated_hour_task["id"]],
        start="2026-10-24T23:00:00Z",
        end="2026-10-25T03:00:00Z",
        policy={
            "working_hours": [
                {
                    "weekday": 6,
                    "start_time": "02:00:00",
                    "end_time": "03:00:00",
                }
            ]
        },
    )
    assert len(repeated_hour_preview["placements"]) == 1
    assert repeated_hour_preview["capacity"]["available_focus_minutes"] == 120


def test_stale_preview_is_rejected(client: TestClient) -> None:
    task = _task(client, "Mutable task", estimated_duration_minutes=60)
    preview = _preview(client, [task["id"]])
    _data(
        client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"revision": task["revision"], "title": "Task changed after preview"},
        )
    )

    stale = client.post(
        "/api/v1/scheduling/apply",
        json={"preview_id": preview["preview_id"]},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_scheduling_preview"


def test_apply_rolls_back_every_task_and_preview_on_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = [
        _task(client, f"Atomic task {index}", estimated_duration_minutes=60) for index in range(2)
    ]
    preview = _preview(client, [task["id"] for task in tasks])
    original_update = TaskRepository.update
    calls = 0

    def fail_second_update(self: TaskRepository, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated second-write failure")
        return original_update(self, *args, **kwargs)

    monkeypatch.setattr(TaskRepository, "update", fail_second_update)
    with pytest.raises(RuntimeError, match="simulated second-write failure"):
        client.post(
            "/api/v1/scheduling/apply",
            json={"preview_id": preview["preview_id"]},
        )

    for task in tasks:
        current = _data(client.get(f"/api/v1/tasks/{task['id']}"))
        assert current["scheduled_start_at"] is None
        assert current["revision"] == task["revision"]
    assert (
        client.get(
            "/api/v1/timeline",
            params={"action": "task_schedule_applied"},
        ).json()["meta"]["total_items"]
        == 0
    )

    monkeypatch.setattr(TaskRepository, "update", original_update)
    applied = client.post(
        "/api/v1/scheduling/apply",
        json={"preview_id": preview["preview_id"]},
    )
    assert applied.status_code == 200, applied.text


def test_timeout_returns_explainable_best_known_result(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task(client, "Time-limited task", estimated_duration_minutes=60)
    monkeypatch.setattr(
        cp_model.CpSolver,
        "solve",
        lambda _solver, _model: cp_model.UNKNOWN,
    )

    preview = _preview(
        client,
        [task["id"]],
        solver_time_limit_seconds=0.001,
    )
    assert preview["solver_status"] == "unknown"
    assert preview["optimality_proven"] is False
    assert preview["placements"] == []
    assert preview["unscheduled_tasks"][0]["reasons"][0]["code"] == "solver_timeout"


def test_conference_and_hackathon_commitments_can_be_scheduled(
    client: TestClient,
) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "scheduling_scenarios.json"
    scenarios = json.loads(fixture_path.read_text(encoding="utf-8"))["scenarios"]
    for scenario in scenarios:
        commitment = _data(
            client.post("/api/v1/commitments", json=scenario["commitment"]),
            201,
        )
        task_ids: list[str] = []
        for task_payload in scenario["tasks"]:
            task = _task(client, **task_payload)
            task_ids.append(task["id"])
            _data(
                client.post(
                    f"/api/v1/commitments/{commitment['id']}/links",
                    json={"entity_type": "task", "entity_id": task["id"]},
                ),
                201,
            )
        preview = _data(
            client.post(
                f"/api/v1/commitments/{commitment['id']}/schedule-preview",
                json=scenario["scope"],
            ),
            201,
        )
        assert preview["commitment_id"] == commitment["id"]
        assert {item["task_id"] for item in preview["placements"]} == set(task_ids)
        assert preview["unscheduled_tasks"] == []


def test_scheduling_routes_are_documented_and_task_suggestions_work(
    client: TestClient,
) -> None:
    task = _task(client, "Single suggestion", estimated_duration_minutes=30)
    suggestion = _data(
        client.post(
            f"/api/v1/tasks/{task['id']}/schedule-suggestions",
            json=_scope(),
        ),
        201,
    )
    assert suggestion["placements"][0]["task_id"] == task["id"]

    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/api/v1/scheduling/preview",
        "/api/v1/scheduling/apply",
        "/api/v1/scheduling/capacity",
        "/api/v1/scheduling/explanations/{preview_id}",
        "/api/v1/tasks/{task_id}/schedule-suggestions",
        "/api/v1/commitments/{commitment_id}/schedule-preview",
    } <= paths.keys()
