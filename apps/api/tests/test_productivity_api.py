from __future__ import annotations

from fastapi.testclient import TestClient


def _create_project(client: TestClient, name: str = "Launch") -> dict[str, object]:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "description_markdown": "# Product launch",
            "target_start_date": "2026-07-15",
            "target_end_date": "2026-08-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_task(client: TestClient, title: str, **values: object) -> dict[str, object]:
    response = client.post("/api/v1/tasks", json={"title": title, **values})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_projects_tasks_dependencies_bulk_actions_and_derived_state(
    client: TestClient,
) -> None:
    project = _create_project(client)
    prerequisite = _create_task(
        client,
        "Prepare release",
        project_id=project["id"],
        due_at="2020-01-01T09:00:00Z",
        priority="high",
    )
    dependent = _create_task(
        client,
        "Publish release",
        project_id=project["id"],
        due_at="2020-01-02T09:00:00Z",
        estimated_duration_minutes=60,
    )

    dependency_response = client.post(
        f"/api/v1/tasks/{dependent['id']}/dependencies",
        json={"depends_on_task_id": prerequisite["id"]},
    )
    assert dependency_response.status_code == 201, dependency_response.text

    blocked = client.get(f"/api/v1/tasks/{dependent['id']}").json()["data"]
    assert blocked["blocked"] is True
    assert blocked["overdue"] is True
    assert blocked["schedulable"] is False

    cycle = client.post(
        f"/api/v1/tasks/{prerequisite['id']}/dependencies",
        json={"depends_on_task_id": dependent["id"]},
    )
    assert cycle.status_code == 409
    assert cycle.json()["error"]["code"] == "task_dependency_cycle"

    blocked_list = client.get(
        "/api/v1/tasks",
        params={"blocked": True, "project_id": project["id"]},
    )
    assert blocked_list.status_code == 200
    assert [item["id"] for item in blocked_list.json()["data"]] == [dependent["id"]]

    completed = client.post(
        "/api/v1/tasks/actions/bulk-complete",
        json={
            "items": [
                {
                    "id": prerequisite["id"],
                    "revision": prerequisite["revision"],
                    "actual_duration_minutes": 45,
                }
            ]
        },
    )
    assert completed.status_code == 200, completed.text
    completed_task = completed.json()["data"][0]
    assert completed_task["status"] == "completed"
    assert completed_task["actual_duration_minutes"] == 45
    assert completed_task["completed_at"] is not None

    unblocked = client.get(f"/api/v1/tasks/{dependent['id']}").json()["data"]
    assert unblocked["blocked"] is False
    assert unblocked["schedulable"] is True

    rescheduled = client.post(
        "/api/v1/tasks/actions/bulk-reschedule",
        json={
            "items": [
                {
                    "id": dependent["id"],
                    "revision": unblocked["revision"],
                    "scheduled_start_at": "2026-07-20T09:00:00+02:00",
                    "scheduled_end_at": "2026-07-20T10:00:00+02:00",
                }
            ]
        },
    )
    assert rescheduled.status_code == 200, rescheduled.text
    assert rescheduled.json()["data"][0]["scheduled_start_at"].endswith("Z")

    progress = client.get(f"/api/v1/projects/{project['id']}")
    assert progress.status_code == 200
    assert progress.json()["data"]["total_tasks"] == 2
    assert progress.json()["data"]["completed_tasks"] == 1
    assert progress.json()["data"]["progress_basis_points"] == 5000


def test_subtasks_recurrence_pagination_and_revision_conflicts(client: TestClient) -> None:
    project = _create_project(client, "Operations")
    parent = _create_task(client, "Parent", project_id=project["id"])
    child = _create_task(
        client,
        "Child",
        project_id=project["id"],
        parent_task_id=parent["id"],
    )
    refreshed_parent = client.get(f"/api/v1/tasks/{parent['id']}").json()["data"]
    assert refreshed_parent["child_count"] == 1

    parent_cycle = client.patch(
        f"/api/v1/tasks/{parent['id']}",
        json={"revision": refreshed_parent["revision"], "parent_task_id": child["id"]},
    )
    assert parent_cycle.status_code == 422
    assert parent_cycle.json()["error"]["code"] == "task_parent_cycle"

    recurring = _create_task(
        client,
        "Water plants",
        due_at="2026-07-15T07:00:00+02:00",
        estimated_duration_minutes=10,
        recurrence={"rrule": "FREQ=DAILY;COUNT=3"},
    )
    occurrences = client.get(
        f"/api/v1/tasks/{recurring['id']}/occurrences",
        params={
            "start": "2026-07-14T00:00:00Z",
            "end": "2026-07-20T00:00:00Z",
        },
    )
    assert occurrences.status_code == 200, occurrences.text
    assert len(occurrences.json()["data"]) == 3
    assert all(item["ends_at"] is not None for item in occurrences.json()["data"])

    page = client.get(
        "/api/v1/tasks",
        params={"page": 2, "page_size": 1, "sort": "title", "order": "asc"},
    )
    assert page.status_code == 200
    assert page.json()["meta"]["total_items"] == 3
    assert page.json()["meta"]["total_pages"] == 3
    assert len(page.json()["data"]) == 1

    first_update = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"revision": project["revision"], "name": "Current name"},
    )
    assert first_update.status_code == 200
    stale_update = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"revision": project["revision"], "name": "Stale name"},
    )
    assert stale_update.status_code == 409
    assert stale_update.json()["error"]["code"] == "revision_conflict"

    archived = client.post(
        f"/api/v1/projects/{project['id']}/archive",
        json={"revision": first_update.json()["data"]["revision"]},
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
