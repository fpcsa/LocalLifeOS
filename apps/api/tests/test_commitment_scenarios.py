from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "commitment_scenarios.json"


def _fixture(name: str) -> dict[str, Any]:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    value = document[name]
    assert isinstance(value, dict)
    return value


def _data(response: Response, expected_status: int = 200) -> dict[str, Any]:
    assert response.status_code == expected_status, response.text
    value = response.json()["data"]
    assert isinstance(value, dict)
    return value


def _categories(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/finance/categories", params={"page_size": 100})
    assert response.status_code == 200, response.text
    return {item["name"]: item["id"] for item in response.json()["data"]}


def _post(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _data(client.post(path, json=payload), 201)


def _link(
    client: TestClient,
    commitment_id: str,
    entity_type: str,
    entity_id: str,
) -> dict[str, Any]:
    return _post(
        client,
        f"/api/v1/commitments/{commitment_id}/links",
        {"entity_type": entity_type, "entity_id": entity_id},
    )


def _without_category(payload: dict[str, Any], category_id: str) -> dict[str, Any]:
    return {
        **{key: value for key, value in payload.items() if key != "category"},
        "category_id": category_id,
    }


def _build_openai_week(client: TestClient) -> dict[str, Any]:
    scenario = _fixture("openai_build_week")
    project = _post(client, "/api/v1/projects", scenario["project"])
    tasks = [
        _post(
            client,
            "/api/v1/tasks",
            {**task_payload, "project_id": project["id"]},
        )
        for task_payload in scenario["tasks"]
    ]
    commitment = _post(client, "/api/v1/commitments", scenario["commitment"])
    _link(client, commitment["id"], "project", project["id"])
    for task in tasks:
        _link(client, commitment["id"], "task", task["id"])
    return {
        "scenario": scenario,
        "commitment": commitment,
        "project": project,
        "tasks": tasks,
    }


def _build_laptop_purchase(client: TestClient) -> dict[str, Any]:
    scenario = _fixture("laptop_purchase")
    categories = _categories(client)
    account = _post(client, "/api/v1/finance/accounts", scenario["account"])
    plan_payload = _without_category(
        {**scenario["plan"], "account_id": account["id"]},
        categories[scenario["plan"]["category"]],
    )
    plan = _post(client, "/api/v1/finance/transactions/planned", plan_payload)
    commitment = _post(client, "/api/v1/commitments", scenario["commitment"])
    _link(client, commitment["id"], "planned_transaction", plan["id"])
    return {
        "scenario": scenario,
        "commitment": commitment,
        "account": account,
        "plan": plan,
    }


def _build_berlin_conference(client: TestClient) -> dict[str, Any]:
    scenario = _fixture("berlin_tech_conference")
    categories = _categories(client)
    project = _post(client, "/api/v1/projects", scenario["project"])
    linked_tasks = [
        _post(
            client,
            "/api/v1/tasks",
            {**task_payload, "project_id": project["id"]},
        )
        for task_payload in scenario["linked_tasks"]
    ]
    prerequisite = _post(
        client,
        "/api/v1/tasks",
        {**scenario["missing_prerequisite"], "project_id": project["id"]},
    )
    dependency = _post(
        client,
        f"/api/v1/tasks/{linked_tasks[0]['id']}/dependencies",
        {"depends_on_task_id": prerequisite["id"]},
    )
    conference_event = _post(
        client,
        "/api/v1/calendar/events",
        scenario["conference_event"],
    )
    conflicting_event = _post(
        client,
        "/api/v1/calendar/events",
        scenario["conflicting_event"],
    )
    note = _post(client, "/api/v1/notes", scenario["note"])
    account = _post(client, "/api/v1/finance/accounts", scenario["account"])
    expense_plans = [
        _post(
            client,
            "/api/v1/finance/transactions/planned",
            _without_category(
                {**plan_payload, "account_id": account["id"]},
                categories[plan_payload["category"]],
            ),
        )
        for plan_payload in scenario["expense_plans"]
    ]
    income_plan = _post(
        client,
        "/api/v1/finance/transactions/planned",
        _without_category(
            {**scenario["income_plan"], "account_id": account["id"]},
            categories[scenario["income_plan"]["category"]],
        ),
    )
    actual = _post(
        client,
        "/api/v1/finance/transactions",
        _without_category(
            {**scenario["actual_expense"], "account_id": account["id"]},
            categories[scenario["actual_expense"]["category"]],
        ),
    )
    budget_payload = {
        **{key: value for key, value in scenario["budget"].items() if key != "limits"},
        "limits": [
            {
                "category_id": categories[limit["category"]],
                "limit_minor": limit["limit_minor"],
            }
            for limit in scenario["budget"]["limits"]
        ],
    }
    budget = _post(client, "/api/v1/finance/budgets", budget_payload)
    savings_goal = _post(
        client,
        "/api/v1/finance/savings-goals",
        {**scenario["savings_goal"], "account_id": account["id"]},
    )
    general_goal = _post(client, "/api/v1/goals", scenario["general_goal"])
    commitment = _post(client, "/api/v1/commitments", scenario["commitment"])

    _link(client, commitment["id"], "project", project["id"])
    for task in linked_tasks:
        _link(client, commitment["id"], "task", task["id"])
    _link(client, commitment["id"], "calendar_event", conference_event["id"])
    _link(client, commitment["id"], "note", note["id"])
    for plan in [*expense_plans, income_plan]:
        _link(client, commitment["id"], "planned_transaction", plan["id"])
    _link(client, commitment["id"], "transaction", actual["id"])
    _link(client, commitment["id"], "budget", budget["id"])
    _link(client, commitment["id"], "savings_goal", savings_goal["id"])
    _link(client, commitment["id"], "goal", general_goal["id"])
    return {
        "scenario": scenario,
        "commitment": commitment,
        "project": project,
        "linked_tasks": linked_tasks,
        "prerequisite": prerequisite,
        "dependency": dependency,
        "conference_event": conference_event,
        "conflicting_event": conflicting_event,
        "note": note,
        "account": account,
        "expense_plans": expense_plans,
        "income_plan": income_plan,
        "actual": actual,
        "budget": budget,
        "savings_goal": savings_goal,
        "general_goal": general_goal,
    }


def _assessment(client: TestClient, commitment_id: str) -> dict[str, Any]:
    return _data(client.get(f"/api/v1/commitments/{commitment_id}/assessment"))


def _all_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        keys = [str(key) for key in value]
        return keys + [nested for child in value.values() for nested in _all_keys(child)]
    if isinstance(value, list):
        return [nested for child in value for nested in _all_keys(child)]
    return []


def test_time_only_and_finance_only_synthetic_assessments(client: TestClient) -> None:
    build_week = _build_openai_week(client)
    build_assessment = _assessment(client, build_week["commitment"]["id"])
    build_expected = build_week["scenario"]["expected"]
    assert build_assessment["overall_status"] == build_expected["overall_status"]
    assert build_assessment["time_capacity_status"]["status"] == "ok"
    assert build_assessment["financial_capacity_status"]["status"] == "not_applicable"
    assert (
        build_assessment["impact"]["time"]["required_task_duration_minutes"]
        == (build_expected["required_task_duration_minutes"])
    )
    assert (
        build_assessment["impact"]["time"]["scheduled_task_duration_minutes"]
        == (build_expected["scheduled_task_duration_minutes"])
    )
    assert build_assessment["impact"]["time"]["unscheduled_required_work_minutes"] == 0
    assert build_assessment["warnings"] == []

    laptop = _build_laptop_purchase(client)
    laptop_assessment = _assessment(client, laptop["commitment"]["id"])
    laptop_expected = laptop["scenario"]["expected"]
    assert laptop_assessment["overall_status"] == laptop_expected["overall_status"]
    assert laptop_assessment["time_capacity_status"]["status"] == "not_applicable"
    assert laptop_assessment["financial_capacity_status"]["status"] == "critical"
    money = laptop_assessment["impact"]["currencies"]
    assert money == [
        {
            "currency": "EUR",
            "planned_cost_minor": laptop_expected["planned_cost_minor"],
            "actual_cost_minor": 0,
            "expected_income_minor": 0,
            "ledger_balance_minor": 180_000,
            "projected_available_minor": laptop_expected["projected_available_minor"],
            "required_financial_buffer_minor": laptop_expected["required_financial_buffer_minor"],
            "financial_buffer_violation": True,
        }
    ]
    assert {item["code"] for item in laptop_assessment["warnings"]} == {
        "financial_buffer_violation"
    }


def test_full_conference_assessment_is_deterministic_and_traceable(
    client: TestClient,
) -> None:
    built = _build_berlin_conference(client)
    commitment_id = built["commitment"]["id"]
    assessment = _assessment(client, commitment_id)
    impact = assessment["impact"]

    assert assessment["overall_status"] == "critical"
    assert assessment["time_capacity_status"]["status"] == "warning"
    assert assessment["financial_capacity_status"]["status"] == "critical"
    assert assessment["dependency_status"]["status"] == "critical"
    assert assessment["schedule_conflict_status"]["status"] == "critical"
    assert assessment["goal_impact_status"]["status"] == "critical"
    assert impact["currencies"] == [
        {
            "currency": "EUR",
            "planned_cost_minor": 117_000,
            "actual_cost_minor": 10_000,
            "expected_income_minor": 20_000,
            "ledger_balance_minor": 190_000,
            "projected_available_minor": 93_000,
            "required_financial_buffer_minor": 100_000,
            "financial_buffer_violation": True,
        }
    ]
    assert impact["time"] == {
        "required_task_duration_minutes": 600,
        "scheduled_task_duration_minutes": 240,
        "preparation_minutes": 60,
        "travel_minutes": 30,
        "recovery_minutes": 30,
        "time_capacity_requirement_minutes": 720,
        "unscheduled_required_work_minutes": 360,
        "unscheduled_task_ids": [built["linked_tasks"][0]["id"]],
    }
    assert impact["dependencies"]["missing_dependency_ids"] == [built["prerequisite"]["id"]]
    assert impact["dependencies"]["blocked_task_ids"] == [built["linked_tasks"][0]["id"]]
    assert len(impact["calendar_conflicts"]) == 1
    conflict = impact["calendar_conflicts"][0]
    assert {conflict["first_event_id"], conflict["second_event_id"]} == {
        built["conference_event"]["id"],
        built["conflicting_event"]["id"],
    }
    assert impact["budgets"] == [
        {
            "budget_id": built["budget"]["id"],
            "name": "August conference spending",
            "currency": "EUR",
            "total_limit_minor": 100_000,
            "total_actual_minor": 0,
            "total_planned_minor": 117_000,
            "commitment_planned_minor": 117_000,
            "remaining_after_planned_minor": -17_000,
            "violation": True,
        }
    ]
    assert impact["savings_goals"] == [
        {
            "savings_goal_id": built["savings_goal"]["id"],
            "name": "Emergency fund",
            "currency": "EUR",
            "target_minor": 300_000,
            "current_minor": 150_000,
            "commitment_outflow_minor": 117_000,
            "projected_current_minor": 33_000,
            "projected_remaining_minor": 267_000,
            "delayed": True,
        }
    ]

    warnings_by_code = {item["code"]: item for item in assessment["warnings"]}
    assert set(built["scenario"]["expected_warning_codes"]) <= warnings_by_code.keys()
    assert all(item["contributing_entities"] for item in assessment["warnings"])
    assert {
        item["entity_id"] for item in warnings_by_code["calendar_conflict"]["contributing_entities"]
    } == {built["conference_event"]["id"], built["conflicting_event"]["id"]}
    assert built["prerequisite"]["id"] in {
        item["entity_id"]
        for item in warnings_by_code["missing_dependencies"]["contributing_entities"]
    }
    assert all(item["contributing_entities"] for item in assessment["suggested_actions"])
    assert "No aggregate feasibility score" in " ".join(assessment["assumptions"])
    assert not any("score" in key.lower() for key in _all_keys(assessment))

    impact_endpoint = _data(client.get(f"/api/v1/commitments/{commitment_id}/impact"))
    assert impact_endpoint == impact
    warnings_endpoint = _data(client.get(f"/api/v1/commitments/{commitment_id}/warnings"))
    assert warnings_endpoint["overall_status"] == assessment["overall_status"]
    assert warnings_endpoint["warnings"] == assessment["warnings"]
    assert warnings_endpoint["suggested_actions"] == assessment["suggested_actions"]

    before_timeline = client.get(
        "/api/v1/timeline",
        params={"entity_type": "commitment", "page_size": 100},
    ).json()["meta"]["total_items"]
    first_refresh = _data(client.post(f"/api/v1/commitments/{commitment_id}/refresh"))
    second_refresh = _data(client.post(f"/api/v1/commitments/{commitment_id}/refresh"))
    after_timeline = client.get(
        "/api/v1/timeline",
        params={"entity_type": "commitment", "page_size": 100},
    ).json()["meta"]["total_items"]
    first_without_timestamp = deepcopy(first_refresh)
    second_without_timestamp = deepcopy(second_refresh)
    first_without_timestamp.pop("calculated_at")
    second_without_timestamp.pop("calculated_at")
    assert first_without_timestamp == second_without_timestamp
    assert after_timeline == before_timeline
    current = _data(client.get(f"/api/v1/commitments/{commitment_id}"))
    assert current["revision"] == built["commitment"]["revision"]


def test_unified_timeline_filters_ordering_pagination_and_privacy(
    client: TestClient,
) -> None:
    built = _build_berlin_conference(client)
    commitment_id = built["commitment"]["id"]
    response = client.get(
        "/api/v1/timeline/unified",
        params={"page_size": 100, "order": "asc"},
    )
    assert response.status_code == 200, response.text
    items = response.json()["data"]
    occurred = [
        datetime.fromisoformat(item["occurred_at"].replace("Z", "+00:00")) for item in items
    ]
    assert occurred == sorted(occurred)
    assert {
        "task",
        "calendar_event",
        "note",
        "transaction",
        "planned_transaction",
        "savings_goal",
        "goal",
        "commitment",
    } <= {item["entity_type"] for item in items}

    serialized = json.dumps(response.json())
    assert built["scenario"]["note"]["markdown"] not in serialized
    assert built["scenario"]["actual_expense"]["note"] not in serialized
    assert built["scenario"]["actual_expense"]["payee"] not in serialized
    assert built["scenario"]["expense_plans"][0]["payee"] not in serialized
    finance_items = [
        item for item in items if item["entity_type"] in {"transaction", "planned_transaction"}
    ]
    assert finance_items
    assert all(item["sensitive"] is True for item in finance_items)
    assert {item["title"] for item in finance_items} <= {
        "Expense transaction",
        "Planned expense",
        "Planned income",
    }
    assert all(
        {reference["entity_id"] for reference in item["related_entities"]} >= {commitment_id}
        for item in finance_items
    )

    page_one = client.get(
        "/api/v1/timeline/unified",
        params={"page": 1, "page_size": 2, "order": "asc"},
    ).json()
    page_two = client.get(
        "/api/v1/timeline/unified",
        params={"page": 2, "page_size": 2, "order": "asc"},
    ).json()
    assert page_one["meta"]["total_items"] == len(items)
    assert len(page_one["data"]) == 2
    assert {item["item_id"] for item in page_one["data"]}.isdisjoint(
        {item["item_id"] for item in page_two["data"]}
    )

    actual_filter = client.get(
        "/api/v1/timeline/unified",
        params={"entity_type": "transaction", "entity_id": built["actual"]["id"]},
    )
    assert actual_filter.status_code == 200, actual_filter.text
    assert [item["entity_id"] for item in actual_filter.json()["data"]] == [built["actual"]["id"]]
    range_filter = client.get(
        "/api/v1/timeline/unified",
        params={
            "start": "2026-08-10T00:00:00Z",
            "end": "2026-08-11T00:00:00Z",
            "entity_type": "calendar_event",
        },
    )
    assert range_filter.status_code == 200, range_filter.text
    assert {item["entity_id"] for item in range_filter.json()["data"]} == {
        built["conference_event"]["id"],
        built["conflicting_event"]["id"],
    }
    invalid_range = client.get(
        "/api/v1/timeline/unified",
        params={
            "start": "2026-08-11T00:00:00Z",
            "end": "2026-08-10T00:00:00Z",
        },
    )
    assert invalid_range.status_code == 422

    commitment_timeline = client.get(
        f"/api/v1/commitments/{commitment_id}/timeline",
        params={"page_size": 100, "order": "asc"},
    )
    assert commitment_timeline.status_code == 200, commitment_timeline.text
    commitment_items = commitment_timeline.json()["data"]
    assert built["conference_event"]["id"] in {item["entity_id"] for item in commitment_items}
    assert built["conflicting_event"]["id"] not in {item["entity_id"] for item in commitment_items}
    plan_filter = client.get(
        f"/api/v1/commitments/{commitment_id}/timeline",
        params={"entity_type": "planned_transaction", "page_size": 100},
    )
    assert plan_filter.status_code == 200, plan_filter.text
    assert plan_filter.json()["meta"]["total_items"] == 3
