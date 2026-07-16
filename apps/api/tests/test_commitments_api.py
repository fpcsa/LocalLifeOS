from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.models import CommitmentEntityLink
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, col, select


def _data(response: Response, expected_status: int = 200) -> dict[str, Any]:
    assert response.status_code == expected_status, response.text
    value = response.json()["data"]
    assert isinstance(value, dict)
    return value


def _list_data(response: Response, expected_status: int = 200) -> list[dict[str, Any]]:
    assert response.status_code == expected_status, response.text
    value = response.json()["data"]
    assert isinstance(value, list)
    return value


def _create_commitment(client: TestClient, **values: object) -> dict[str, Any]:
    return _data(
        client.post(
            "/api/v1/commitments",
            json={"title": "A considered commitment", **values},
        ),
        201,
    )


def _link(
    client: TestClient,
    commitment_id: str,
    entity_type: str,
    entity_id: str,
    *,
    role: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, object] = {
        "entity_type": entity_type,
        "entity_id": entity_id,
    }
    if role is not None:
        payload["role"] = role
    return _data(
        client.post(f"/api/v1/commitments/{commitment_id}/links", json=payload),
        201,
    )


def _categories(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/finance/categories", params={"page_size": 100})
    assert response.status_code == 200, response.text
    return {item["name"]: item["id"] for item in response.json()["data"]}


def test_commitment_crud_filters_empty_assessment_and_concurrency(
    client: TestClient,
) -> None:
    empty = _create_commitment(client)
    assert empty["status"] == "draft"
    assert empty["links"] == []

    assessment = _data(client.get(f"/api/v1/commitments/{empty['id']}/assessment"))
    component_names = (
        "time_capacity_status",
        "financial_capacity_status",
        "dependency_status",
        "schedule_conflict_status",
        "goal_impact_status",
        "deadline_status",
    )
    assert assessment["overall_status"] == "not_applicable"
    assert all(assessment[name]["status"] == "not_applicable" for name in component_names)
    assert assessment["warnings"] == []
    assert assessment["suggested_actions"] == []
    assert assessment["impact"]["currencies"] == []
    assert assessment["impact"]["time"]["time_capacity_requirement_minutes"] == 0

    impact = _data(client.get(f"/api/v1/commitments/{empty['id']}/impact"))
    assert impact == assessment["impact"]
    warnings = _data(client.get(f"/api/v1/commitments/{empty['id']}/warnings"))
    assert warnings["overall_status"] == "not_applicable"
    assert warnings["warnings"] == []

    later = _create_commitment(
        client,
        title="Berlin option",
        category="travel",
        status="planned",
        target_end_at="2026-09-01T18:00:00+02:00",
    )
    filtered = client.get(
        "/api/v1/commitments",
        params={
            "q": "Berlin",
            "category": "travel",
            "status": "planned",
            "target_before": "2026-10-01T00:00:00Z",
            "page_size": 1,
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 1,
        "total_pages": 1,
    }
    assert filtered.json()["data"][0]["id"] == later["id"]

    updated = _data(
        client.patch(
            f"/api/v1/commitments/{empty['id']}",
            json={
                "revision": empty["revision"],
                "title": "A deliberate commitment",
                "category": "personal",
                "status": "active",
            },
        )
    )
    assert updated["revision"] == empty["revision"] + 1
    assert updated["title"] == "A deliberate commitment"
    stale = client.patch(
        f"/api/v1/commitments/{empty['id']}",
        json={"revision": empty["revision"], "title": "Stale title"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "revision_conflict"

    invalid_range = client.post(
        "/api/v1/commitments",
        json={
            "title": "Impossible range",
            "target_start_at": "2026-09-02T10:00:00Z",
            "target_end_at": "2026-09-02T09:00:00Z",
        },
    )
    assert invalid_range.status_code == 422


def test_commitment_links_archive_and_delete_lifecycle(
    client: TestClient,
    db_session: Session,
) -> None:
    commitment = _create_commitment(client, category="integration")
    categories = _categories(client)
    account = _data(
        client.post(
            "/api/v1/finance/accounts",
            json={
                "name": "Integration account",
                "account_type": "checking",
                "currency_code": "EUR",
                "opening_balance_minor": 100_000,
            },
        ),
        201,
    )
    project = _data(client.post("/api/v1/projects", json={"name": "Linked project"}), 201)
    task = _data(client.post("/api/v1/tasks", json={"title": "Linked task"}), 201)
    event = _data(
        client.post(
            "/api/v1/calendar/events",
            json={
                "title": "Linked event",
                "timezone": "Europe/Rome",
                "starts_at": "2026-08-01T10:00:00+02:00",
                "ends_at": "2026-08-01T11:00:00+02:00",
            },
        ),
        201,
    )
    note = _data(
        client.post(
            "/api/v1/notes",
            json={"title": "Linked note", "markdown": "Private body"},
        ),
        201,
    )
    planned = _data(
        client.post(
            "/api/v1/finance/transactions/planned",
            json={
                "account_id": account["id"],
                "category_id": categories["Other expense"],
                "transaction_type": "expense",
                "amount_minor": 5_000,
                "currency_code": "EUR",
                "planned_for": "2026-08-02T10:00:00+02:00",
            },
        ),
        201,
    )
    actual = _data(
        client.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": account["id"],
                "category_id": categories["Other expense"],
                "transaction_type": "expense",
                "amount_minor": 1_000,
                "currency_code": "EUR",
                "occurred_at": "2026-07-01T10:00:00+02:00",
            },
        ),
        201,
    )
    budget = _data(
        client.post(
            "/api/v1/finance/budgets",
            json={
                "name": "Linked budget",
                "period": "monthly",
                "start_date": "2026-08-01",
                "currency_code": "EUR",
                "limits": [
                    {
                        "category_id": categories["Other expense"],
                        "limit_minor": 20_000,
                    }
                ],
            },
        ),
        201,
    )
    savings = _data(
        client.post(
            "/api/v1/finance/savings-goals",
            json={
                "name": "Linked savings goal",
                "account_id": account["id"],
                "target_minor": 50_000,
                "current_minor": 10_000,
                "currency_code": "EUR",
            },
        ),
        201,
    )
    goal = _data(
        client.post(
            "/api/v1/goals",
            json={"title": "Linked general goal", "progress_basis_points": 1_000},
        ),
        201,
    )
    targets = {
        "project": project,
        "task": task,
        "calendar_event": event,
        "note": note,
        "planned_transaction": planned,
        "transaction": actual,
        "budget": budget,
        "savings_goal": savings,
        "goal": goal,
    }
    links = {
        entity_type: _link(
            client,
            commitment["id"],
            entity_type,
            target["id"],
            role="supporting" if entity_type == "note" else None,
        )
        for entity_type, target in targets.items()
    }
    assert set(links) == {
        "project",
        "task",
        "calendar_event",
        "note",
        "planned_transaction",
        "transaction",
        "budget",
        "savings_goal",
        "goal",
    }
    stored = _list_data(client.get(f"/api/v1/commitments/{commitment['id']}/links"))
    assert len(stored) == 9
    assert next(item for item in stored if item["entity_type"] == "note")["role"] == "supporting"

    duplicate = client.post(
        f"/api/v1/commitments/{commitment['id']}/links",
        json={"entity_type": "task", "entity_id": task["id"]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_commitment_link"
    missing_target = client.post(
        f"/api/v1/commitments/{commitment['id']}/links",
        json={"entity_type": "task", "entity_id": str(uuid4())},
    )
    assert missing_target.status_code == 422
    assert missing_target.json()["error"]["code"] == "invalid_commitment_target"

    removed = client.delete(f"/api/v1/commitments/{commitment['id']}/links/{links['task']['id']}")
    assert removed.status_code == 200, removed.text
    links["task"] = _link(client, commitment["id"], "task", task["id"])

    deleted_note = client.delete(
        f"/api/v1/notes/{note['id']}",
        params={"revision": note["revision"]},
    )
    assert deleted_note.status_code == 200, deleted_note.text
    remaining_links = _list_data(client.get(f"/api/v1/commitments/{commitment['id']}/links"))
    assert "note" not in {item["entity_type"] for item in remaining_links}

    archived = _data(
        client.post(
            f"/api/v1/commitments/{commitment['id']}/archive",
            json={"revision": commitment["revision"]},
        )
    )
    assert archived["status"] == "archived"
    default_list = client.get("/api/v1/commitments")
    assert commitment["id"] not in {item["id"] for item in default_list.json()["data"]}
    with_archived = client.get("/api/v1/commitments", params={"include_archived": True})
    assert commitment["id"] in {item["id"] for item in with_archived.json()["data"]}
    assert len(archived["links"]) == 8

    immutable = client.patch(
        f"/api/v1/commitments/{commitment['id']}",
        json={"revision": archived["revision"], "title": "Cannot change"},
    )
    assert immutable.status_code == 409
    assert immutable.json()["error"]["code"] == "commitment_archived"
    cannot_link = client.post(
        f"/api/v1/commitments/{commitment['id']}/links",
        json={"entity_type": "note", "entity_id": note["id"]},
    )
    assert cannot_link.status_code == 409
    cannot_unlink = client.delete(
        f"/api/v1/commitments/{commitment['id']}/links/{links['task']['id']}"
    )
    assert cannot_unlink.status_code == 409

    deleted = client.delete(
        f"/api/v1/commitments/{commitment['id']}",
        params={"revision": archived["revision"]},
    )
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/api/v1/commitments/{commitment['id']}").status_code == 404
    link_rows = db_session.exec(
        select(CommitmentEntityLink).where(
            col(CommitmentEntityLink.commitment_id) == UUID(commitment["id"])
        )
    ).all()
    assert link_rows == []


def test_commitment_and_unified_timeline_routes_are_documented(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/commitments",
        "/api/v1/commitments/{commitment_id}",
        "/api/v1/commitments/{commitment_id}/archive",
        "/api/v1/commitments/{commitment_id}/links",
        "/api/v1/commitments/{commitment_id}/links/{link_id}",
        "/api/v1/commitments/{commitment_id}/assessment",
        "/api/v1/commitments/{commitment_id}/impact",
        "/api/v1/commitments/{commitment_id}/warnings",
        "/api/v1/commitments/{commitment_id}/timeline",
        "/api/v1/commitments/{commitment_id}/refresh",
        "/api/v1/timeline/unified",
    }
    assert expected <= paths.keys()
