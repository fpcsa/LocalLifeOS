from __future__ import annotations

from fastapi.testclient import TestClient


def _create_event(client: TestClient, title: str, **values: object) -> dict[str, object]:
    response = client.post(
        "/api/v1/calendar/events",
        json={"title": title, "timezone": "Europe/Rome", **values},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_calendar_range_conflicts_buffers_move_resize_and_links(client: TestClient) -> None:
    project_response = client.post("/api/v1/projects", json={"name": "Conference"})
    assert project_response.status_code == 201
    project = project_response.json()["data"]

    first = _create_event(
        client,
        "Keynote",
        starts_at="2026-07-15T10:00:00+02:00",
        ends_at="2026-07-15T11:00:00+02:00",
        category="work",
        location="Local hall",
        recovery_buffer_minutes=15,
        linked_entities=[{"entity_type": "project", "entity_id": project["id"]}],
    )
    second = _create_event(
        client,
        "Interview",
        starts_at="2026-07-15T11:10:00+02:00",
        ends_at="2026-07-15T12:00:00+02:00",
        preparation_buffer_minutes=5,
        travel_buffer_minutes=5,
    )
    assert first["linked_entities"][0]["entity_id"] == project["id"]

    params = {
        "start": "2026-07-15T00:00:00Z",
        "end": "2026-07-16T00:00:00Z",
        "timezone": "Europe/Rome",
    }
    ranged = client.get("/api/v1/calendar/events", params=params)
    assert ranged.status_code == 200, ranged.text
    assert ranged.json()["meta"]["total_items"] == 2

    conflicts = client.get("/api/v1/calendar/conflicts", params=params)
    assert conflicts.status_code == 200, conflicts.text
    assert len(conflicts.json()["data"]) == 1
    conflict = conflicts.json()["data"][0]
    assert {conflict["first"]["event_id"], conflict["second"]["event_id"]} == {
        first["id"],
        second["id"],
    }

    moved = client.post(
        f"/api/v1/calendar/events/{second['id']}/move",
        json={"revision": second["revision"], "starts_at": "2026-07-15T13:00:00+02:00"},
    )
    assert moved.status_code == 200, moved.text
    moved_event = moved.json()["data"]
    assert moved_event["ends_at"] == "2026-07-15T11:50:00Z"

    stale_resize = client.post(
        f"/api/v1/calendar/events/{second['id']}/resize",
        json={"revision": second["revision"], "ends_at": "2026-07-15T14:00:00+02:00"},
    )
    assert stale_resize.status_code == 409
    assert stale_resize.json()["error"]["code"] == "revision_conflict"

    resized = client.post(
        f"/api/v1/calendar/events/{second['id']}/resize",
        json={"revision": moved_event["revision"], "ends_at": "2026-07-15T14:30:00+02:00"},
    )
    assert resized.status_code == 200, resized.text
    assert resized.json()["data"]["ends_at"] == "2026-07-15T12:30:00Z"
    assert client.get("/api/v1/calendar/conflicts", params=params).json()["data"] == []

    category = client.get("/api/v1/calendar/events", params={**params, "category": "work"})
    assert [item["id"] for item in category.json()["data"]] == [first["id"]]


def test_calendar_recurrence_all_day_timezone_and_cancelled_behavior(
    client: TestClient,
) -> None:
    recurring = _create_event(
        client,
        "Daily standup",
        starts_at="2026-07-15T09:00:00+02:00",
        ends_at="2026-07-15T09:15:00+02:00",
        recurrence={"rrule": "FREQ=DAILY;COUNT=3"},
    )
    occurrences = client.get(
        f"/api/v1/calendar/events/{recurring['id']}/occurrences",
        params={
            "start": "2026-07-14T00:00:00Z",
            "end": "2026-07-20T00:00:00Z",
        },
    )
    assert occurrences.status_code == 200, occurrences.text
    assert len(occurrences.json()["data"]) == 3

    all_day = _create_event(
        client,
        "Holiday",
        all_day=True,
        all_day_start="2026-07-16",
        all_day_end="2026-07-17",
    )
    overnight = _create_event(
        client,
        "Late arrival",
        starts_at="2026-07-15T23:30:00+00:00",
        ends_at="2026-07-16T00:30:00+00:00",
    )
    params = {
        "start": "2026-07-15T20:00:00Z",
        "end": "2026-07-16T02:00:00Z",
        "timezone": "Europe/Rome",
    }
    conflicts = client.get("/api/v1/calendar/conflicts", params=params)
    assert conflicts.status_code == 200
    pairs = [
        {item["first"]["event_id"], item["second"]["event_id"]} for item in conflicts.json()["data"]
    ]
    assert {all_day["id"], overnight["id"]} in pairs

    cancelled = client.patch(
        f"/api/v1/calendar/events/{overnight['id']}",
        json={"revision": overnight["revision"], "status": "cancelled"},
    )
    assert cancelled.status_code == 200
    assert client.get("/api/v1/calendar/conflicts", params=params).json()["data"] == []
    cancelled_list = client.get(
        "/api/v1/calendar/events",
        params={**params, "status": "cancelled"},
    )
    assert [item["id"] for item in cancelled_list.json()["data"]] == [overnight["id"]]

    naive_range = client.get(
        "/api/v1/calendar/events",
        params={"start": "2026-07-15T00:00:00", "end": "2026-07-16T00:00:00"},
    )
    assert naive_range.status_code == 422


def test_productivity_routes_are_documented_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/projects",
        "/api/v1/tasks",
        "/api/v1/notes",
        "/api/v1/attachments",
        "/api/v1/calendar/events",
        "/api/v1/calendar/conflicts",
    }
    assert expected <= paths.keys()
