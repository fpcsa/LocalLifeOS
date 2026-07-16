from __future__ import annotations

from app.services.demo_data import IDS
from fastapi.testclient import TestClient


def _data(response, expected_status: int = 200):  # type: ignore[no-untyped-def]
    assert response.status_code == expected_status, response.text
    return response.json()["data"]


def test_demo_loader_is_deterministic_complete_and_openapi_documented(
    client: TestClient,
) -> None:
    first = _data(client.post("/api/v1/demo/load"))
    second = _data(client.post("/api/v1/demo/load"))

    assert first == second
    assert first["synthetic"] is True
    assert first["anchor_date"] == "2026-07-16"
    assert first["records_created"]["Scenario"] == 5
    assert first["records_created"]["Attachment"] == 2
    assert first["conflict_count"] >= 2
    assert first["budget_shortfall_count"] >= 1

    schema = client.get("/openapi.json").json()
    assert "/api/v1/demo/load" in schema["paths"]
    assert "/api/v1/demo/reset" in schema["paths"]


def test_demo_invariants_are_real_service_results(client: TestClient) -> None:
    _data(client.post("/api/v1/demo/load"))

    conflicts = _data(
        client.get(
            "/api/v1/calendar/conflicts",
            params={
                "start": "2026-07-19T00:00:00Z",
                "end": "2026-07-23T00:00:00Z",
                "timezone": "Europe/Rome",
            },
        )
    )
    assert len(conflicts) >= 2

    consumption = _data(client.get(f"/api/v1/finance/budgets/{IDS['budget_july']}/consumption"))
    food = next(item for item in consumption["categories"] if item["category_name"] == "Food")
    assert food["actual_minor"] > food["limit_minor"]

    scenarios = client.get("/api/v1/scenarios").json()["data"]
    assert {item["name"] for item in scenarios} >= {
        "Berlin · physical attendance",
        "Berlin · remote attendance",
        "Berlin · skip conference",
        "Laptop purchase · August",
        "Laptop purchase · October",
    }

    compared = _data(
        client.post(
            "/api/v1/scenarios/compare",
            json={
                "scenario_ids": [
                    str(IDS["scenario_physical"]),
                    str(IDS["scenario_remote"]),
                    str(IDS["scenario_skip"]),
                ]
            },
        )
    )
    assert len(compared["previews"]) == 3

    rules = client.get("/api/v1/automation/rules").json()["data"]
    assert {rule["name"] for rule in rules} >= {
        "Overdue task review note",
        "Weekly backup reminder",
    }


def test_demo_reset_removes_only_reserved_records(client: TestClient) -> None:
    own_project = _data(client.post("/api/v1/projects", json={"name": "Keep me"}), 201)
    _data(client.post("/api/v1/demo/load"))

    removed = _data(client.post("/api/v1/demo/reset"))
    assert removed["records_removed"] > 0
    assert removed["attachment_files_removed"] == 2
    assert _data(client.get(f"/api/v1/projects/{own_project['id']}"))["name"] == "Keep me"
    assert client.get(f"/api/v1/projects/{IDS['project_build_week']}").status_code == 404
