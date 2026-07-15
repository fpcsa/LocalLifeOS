from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from httpx import Response


def _data(response: Response, expected_status: int = 200) -> dict[str, Any]:
    assert response.status_code == expected_status, response.text
    value = response.json()["data"]
    assert isinstance(value, dict)
    return value


def _account(
    client: TestClient,
    name: str,
    currency: str,
    opening: int,
    buffer: int = 0,
) -> dict[str, Any]:
    return _data(
        client.post(
            "/api/v1/finance/accounts",
            json={
                "name": name,
                "account_type": "checking",
                "currency_code": currency,
                "opening_balance_minor": opening,
                "financial_buffer_minor": buffer,
            },
        ),
        201,
    )


def _categories(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/finance/categories", params={"page_size": 100})
    assert response.status_code == 200
    return {item["name"]: item["id"] for item in response.json()["data"]}


def _post_transaction(
    client: TestClient,
    account_id: str,
    category_id: str,
    transaction_type: str,
    amount_minor: int,
    currency: str,
    occurred_at: str,
) -> dict[str, Any]:
    return _data(
        client.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": account_id,
                "category_id": category_id,
                "transaction_type": transaction_type,
                "amount_minor": amount_minor,
                "currency_code": currency,
                "occurred_at": occurred_at,
            },
        ),
        201,
    )


def test_recurring_generation_is_idempotent_and_lifecycle_is_enforced(
    client: TestClient,
) -> None:
    account = _account(client, "Income", "EUR", 0)
    salary_id = _categories(client)["Salary"]
    rule = _data(
        client.post(
            "/api/v1/finance/recurring",
            json={
                "name": "Monthly salary",
                "account_id": account["id"],
                "category_id": salary_id,
                "transaction_type": "income",
                "amount_minor": 200_000,
                "currency_code": "EUR",
                "rrule": "RRULE:FREQ=MONTHLY;COUNT=3",
                "starts_at": "2026-07-01T09:00:00+02:00",
                "is_committed": True,
            },
        ),
        201,
    )
    generation = {
        "start": "2026-07-01T00:00:00+02:00",
        "end": "2026-10-01T00:00:00+02:00",
    }
    first = client.post(
        f"/api/v1/finance/recurring/{rule['id']}/generate",
        json=generation,
    )
    assert first.status_code == 200, first.text
    assert len(first.json()["data"]) == 3
    assert len({item["occurrence_key"] for item in first.json()["data"]}) == 3
    second = client.post(
        f"/api/v1/finance/recurring/{rule['id']}/generate",
        json=generation,
    )
    assert second.status_code == 200
    assert second.json()["data"] == []

    paused = _data(
        client.post(
            f"/api/v1/finance/recurring/{rule['id']}/pause",
            json={"revision": rule["revision"]},
        )
    )
    assert paused["status"] == "paused"
    assert (
        client.post(
            f"/api/v1/finance/recurring/{rule['id']}/generate",
            json=generation,
        ).status_code
        == 409
    )
    resumed = _data(
        client.post(
            f"/api/v1/finance/recurring/{rule['id']}/resume",
            json={"revision": paused["revision"]},
        )
    )
    ended = _data(
        client.post(
            f"/api/v1/finance/recurring/{rule['id']}/end",
            json={"revision": resumed["revision"]},
        )
    )
    assert ended["status"] == "ended"
    assert (
        client.post(
            f"/api/v1/finance/recurring/{rule['id']}/resume",
            json={"revision": ended["revision"]},
        ).status_code
        == 409
    )


def test_reports_budgets_multi_currency_and_financial_buffer_are_explainable(
    client: TestClient,
) -> None:
    euro = _account(client, "Euro account", "EUR", 100_000, buffer=320_000)
    usd = _account(client, "Dollar account", "USD", 20_000)
    categories = _categories(client)
    _post_transaction(
        client,
        euro["id"],
        categories["Salary"],
        "income",
        300_000,
        "EUR",
        "2026-07-02T09:00:00+02:00",
    )
    _post_transaction(
        client,
        euro["id"],
        categories["Food"],
        "expense",
        50_000,
        "EUR",
        "2026-07-05T12:00:00+02:00",
    )
    _post_transaction(
        client,
        usd["id"],
        categories["Food"],
        "expense",
        1_000,
        "USD",
        "2026-07-05T12:00:00+02:00",
    )
    _data(
        client.post(
            "/api/v1/finance/transactions/planned",
            json={
                "account_id": euro["id"],
                "category_id": categories["Food"],
                "transaction_type": "expense",
                "amount_minor": 40_000,
                "currency_code": "EUR",
                "planned_for": "2026-07-20T12:00:00+02:00",
                "is_committed": True,
            },
        ),
        201,
    )
    subscription = _data(
        client.post(
            "/api/v1/finance/subscriptions",
            json={
                "name": "Local service",
                "account_id": euro["id"],
                "category_id": categories["Utilities"],
                "amount_minor": 1_000,
                "currency_code": "EUR",
                "billing_rrule": "FREQ=MONTHLY;COUNT=2",
                "starts_at": "2026-07-25T08:00:00+02:00",
                "payee": "Local service",
            },
        ),
        201,
    )
    linked_rule = _data(
        client.post(
            "/api/v1/finance/recurring",
            json={
                "name": "Subscription planner",
                "account_id": euro["id"],
                "category_id": categories["Utilities"],
                "subscription_id": subscription["id"],
                "transaction_type": "expense",
                "amount_minor": 1_000,
                "currency_code": "EUR",
                "rrule": "FREQ=MONTHLY;COUNT=2",
                "starts_at": "2026-07-25T08:00:00+02:00",
            },
        ),
        201,
    )
    budget = _data(
        client.post(
            "/api/v1/finance/budgets",
            json={
                "name": "July spending",
                "period": "monthly",
                "start_date": "2026-07-01",
                "currency_code": "EUR",
                "limits": [{"category_id": categories["Food"], "limit_minor": 100_000}],
            },
        ),
        201,
    )

    spending = _data(
        client.get(
            "/api/v1/finance/reports/spending-by-category",
            params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
        )
    )
    assert [group["currency"] for group in spending["groups"]] == ["EUR", "USD"]
    euro_spending = next(group for group in spending["groups"] if group["currency"] == "EUR")
    assert euro_spending["total_actual_minor"] == 50_000
    assert euro_spending["total_planned_minor"] == 40_000
    assert spending["metadata"]["input_start"] == "2026-07-01"
    assert spending["metadata"]["assumptions"]
    assert spending["metadata"]["included_records"]

    consumption = _data(client.get(f"/api/v1/finance/budgets/{budget['id']}/consumption"))
    assert consumption["total_limit_minor"] == 100_000
    assert consumption["total_actual_minor"] == 50_000
    assert consumption["total_planned_minor"] == 40_000
    assert consumption["categories"][0]["consumption_basis_points"] == 5_000
    assert consumption["categories"][0]["remaining_after_planned_minor"] == 10_000

    committed = _data(
        client.get(
            "/api/v1/finance/reports/committed-balance",
            params={
                "as_of": "2026-07-15",
                "end_date": "2026-07-31",
                "currency": "EUR",
            },
        )
    )
    group = committed["groups"][0]
    assert group["ledger_balance_minor"] == 350_000
    assert group["committed_planned_minor"] == 40_000
    assert group["committed_subscription_minor"] == 1_000
    assert group["committed_total_minor"] == 41_000
    assert group["effectively_available_minor"] == 309_000
    assert group["financial_buffer_minor"] == 320_000
    assert group["buffer_violation"] is True

    cash_flow = _data(
        client.get(
            "/api/v1/finance/reports/cash-flow",
            params={"start_date": "2026-07-01", "months": 2, "currency": "EUR"},
        )
    )
    july = cash_flow["groups"][0]["months"][0]
    assert july["actual_income_minor"] == 300_000
    assert july["actual_expense_minor"] == 50_000
    assert july["planned_expense_minor"] == 40_000
    assert july["recurring_expense_minor"] == 1_000
    assert cash_flow["metadata"]["calculation_timestamp"]

    changed = _data(
        client.patch(
            f"/api/v1/finance/subscriptions/{subscription['id']}",
            json={"revision": subscription["revision"], "amount_minor": 1_250},
        )
    )
    assert changed["price_changes"] == [
        {
            "id": changed["price_changes"][0]["id"],
            "old_amount_minor": 1_000,
            "new_amount_minor": 1_250,
            "delta_minor": 250,
            "detected_at": changed["price_changes"][0]["detected_at"],
        }
    ]
    synced_rule = _data(client.get(f"/api/v1/finance/recurring/{linked_rule['id']}"))
    assert synced_rule["amount_minor"] == 1_250


def test_savings_and_general_goal_progress(client: TestClient) -> None:
    account = _account(client, "Goal savings", "EUR", 0)
    savings_goal = _data(
        client.post(
            "/api/v1/finance/savings-goals",
            json={
                "name": "Emergency fund",
                "account_id": account["id"],
                "target_minor": 10_000,
                "current_minor": 2_500,
                "currency_code": "EUR",
                "target_date": "2026-12-31",
            },
        ),
        201,
    )
    assert savings_goal["progress_basis_points"] == 2_500
    contributed = _data(
        client.post(
            f"/api/v1/finance/savings-goals/{savings_goal['id']}/contributions",
            json={"revision": savings_goal["revision"], "amount_minor": 7_500},
        )
    )
    assert contributed["progress_basis_points"] == 10_000
    assert contributed["remaining_minor"] == 0
    assert contributed["status"] == "completed"

    goal = _data(
        client.post(
            "/api/v1/goals",
            json={
                "title": "Finish the plan",
                "description_markdown": "A **local** goal.",
                "progress_basis_points": 1_000,
            },
        ),
        201,
    )
    completed = _data(
        client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"revision": goal["revision"], "progress_basis_points": 10_000},
        )
    )
    assert completed["status"] == "completed"
