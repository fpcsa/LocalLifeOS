from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from httpx import Response


def _data(response: Response, expected_status: int = 200) -> Any:
    assert response.status_code == expected_status, response.text
    return response.json()["data"]


def test_scenario_preview_acceptance_and_stale_protection(client: TestClient) -> None:
    task = _data(
        client.post(
            "/api/v1/tasks",
            json={"title": "Book conference travel", "estimated_duration_minutes": 60},
        ),
        201,
    )
    scenario = _data(
        client.post(
            "/api/v1/scenarios",
            json={"name": "Remote conference", "description_markdown": "Travel-free option"},
        ),
        201,
    )
    change = _data(
        client.post(
            f"/api/v1/scenarios/{scenario['id']}/changes",
            json={
                "entity_type": "task",
                "entity_id": task["id"],
                "operation": "update",
                "changes": {"estimated_duration_minutes": 15},
            },
        ),
        201,
    )
    assert change["expected_revision"] == task["revision"]

    preview = _data(client.get(f"/api/v1/scenarios/{scenario['id']}/preview"))
    assert preview["stale"] is False
    assert preview["differences"]["time_required_minutes"] == -45
    assert preview["exact_change_plan"][0]["fields"] == [
        {"field": "estimated_duration_minutes", "before": 60, "after": 15}
    ]

    accepted = _data(
        client.post(
            f"/api/v1/scenarios/{scenario['id']}/accept",
            json={
                "revision": preview["scenario"]["revision"],
                "preview_fingerprint": preview["preview_fingerprint"],
            },
        )
    )
    assert accepted["scenario"]["status"] == "accepted"
    assert _data(client.get(f"/api/v1/tasks/{task['id']}"))["estimated_duration_minutes"] == 15

    stale_scenario = _data(
        client.post("/api/v1/scenarios", json={"name": "Stale option"}),
        201,
    )
    _data(
        client.post(
            f"/api/v1/scenarios/{stale_scenario['id']}/changes",
            json={
                "entity_type": "task",
                "entity_id": task["id"],
                "operation": "update",
                "changes": {"estimated_duration_minutes": 30},
            },
        ),
        201,
    )
    current = _data(client.get(f"/api/v1/tasks/{task['id']}"))
    _data(
        client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"revision": current["revision"], "priority": "high"},
        )
    )
    stale_preview = _data(client.get(f"/api/v1/scenarios/{stale_scenario['id']}/preview"))
    assert stale_preview["stale"] is True
    rejected = client.post(
        f"/api/v1/scenarios/{stale_scenario['id']}/accept",
        json={
            "revision": stale_preview["scenario"]["revision"],
            "preview_fingerprint": stale_preview["preview_fingerprint"],
        },
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "scenario_stale"


def test_scenario_compare_is_documented_and_side_by_side(client: TestClient) -> None:
    scenario_ids = [
        _data(client.post("/api/v1/scenarios", json={"name": name}), 201)["id"]
        for name in ("Physical", "Remote")
    ]
    compared = _data(client.post("/api/v1/scenarios/compare", json={"scenario_ids": scenario_ids}))
    assert [item["scenario"]["id"] for item in compared["previews"]] == scenario_ids

    schema = client.get("/openapi.json").json()
    assert "/api/v1/scenarios/{scenario_id}/preview" in schema["paths"]
    assert "/api/v1/scenarios/{scenario_id}/accept" in schema["paths"]


def test_conference_options_compare_money_time_and_calendar_buffers(
    client: TestClient,
) -> None:
    account = _data(
        client.post(
            "/api/v1/finance/accounts",
            json={
                "name": "Conference checking",
                "account_type": "checking",
                "currency_code": "EUR",
                "opening_balance_minor": 500_000,
                "financial_buffer_minor": 100_000,
            },
        ),
        201,
    )
    commitment = _data(
        client.post(
            "/api/v1/commitments",
            json={
                "title": "Berlin conference decision",
                "status": "planned",
                "time_capacity_requirement_minutes": 420,
                "planned_cost_minor": 60_000,
                "financial_buffer_requirement_minor": 100_000,
                "currency_code": "EUR",
            },
        ),
        201,
    )
    plan = _data(
        client.post(
            "/api/v1/finance/transactions/planned",
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount_minor": 60_000,
                "currency_code": "EUR",
                "planned_for": "2026-10-10T08:00:00Z",
                "is_committed": True,
            },
        ),
        201,
    )
    task = _data(
        client.post(
            "/api/v1/tasks",
            json={
                "title": "Prepare attendance",
                "status": "todo",
                "priority": "high",
                "preferred_time_of_day": "any",
                "estimated_duration_minutes": 360,
                "commitment_ids": [commitment["id"]],
            },
        ),
        201,
    )
    event = _data(
        client.post(
            "/api/v1/calendar/events",
            json={
                "title": "Berlin conference",
                "status": "confirmed",
                "all_day": False,
                "starts_at": "2026-10-10T08:00:00Z",
                "ends_at": "2026-10-10T16:00:00Z",
                "timezone": "Europe/Rome",
                "preparation_buffer_minutes": 30,
                "travel_buffer_minutes": 30,
                "recovery_buffer_minutes": 30,
                "commitment_ids": [commitment["id"]],
            },
        ),
        201,
    )

    scenarios: dict[str, str] = {}
    for name, amount, minutes, travel in (
        ("Physical", 165_000, 960, 180),
        ("Remote", 19_000, 360, 0),
    ):
        scenario = _data(client.post("/api/v1/scenarios", json={"name": name}), 201)
        scenarios[name] = scenario["id"]
        changes = (
            ("planned_transaction", plan["id"], {"amount_minor": amount}),
            (
                "commitment",
                commitment["id"],
                {"planned_cost_minor": amount, "time_capacity_requirement_minutes": minutes},
            ),
            ("task", task["id"], {"estimated_duration_minutes": minutes // 2}),
            ("calendar_event", event["id"], {"travel_buffer_minutes": travel}),
        )
        for entity_type, entity_id, changeset in changes:
            _data(
                client.post(
                    f"/api/v1/scenarios/{scenario['id']}/changes",
                    json={
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "operation": "update",
                        "changes": changeset,
                    },
                ),
                201,
            )

    compared = _data(
        client.post(
            "/api/v1/scenarios/compare",
            json={"scenario_ids": [scenarios["Physical"], scenarios["Remote"]]},
        )
    )["previews"]
    physical, remote = compared
    assert (
        physical["projected"]["time_required_minutes"]
        > remote["projected"]["time_required_minutes"]
    )
    physical_eur = next(
        item for item in physical["projected"]["currencies"] if item["currency"] == "EUR"
    )
    remote_eur = next(
        item for item in remote["projected"]["currencies"] if item["currency"] == "EUR"
    )
    assert physical_eur["projected_cash_flow_minor"] < remote_eur["projected_cash_flow_minor"]
    assert physical["exact_change_plan"][0]["entity_type"] == "planned_transaction"
