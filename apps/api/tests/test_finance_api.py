from __future__ import annotations

from typing import Any

import pytest
from app.models import FinancialAccount, FinancialAccountType
from app.services.seed import DEFAULT_WORKSPACE_ID
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session


def _data(response: Response, expected_status: int = 200) -> dict[str, Any]:
    assert response.status_code == expected_status, response.text
    value = response.json()["data"]
    assert isinstance(value, dict)
    return value


def _account(
    client: TestClient,
    name: str,
    *,
    currency: str = "EUR",
    opening: int = 0,
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


def _category_id(client: TestClient, name: str) -> str:
    response = client.get("/api/v1/finance/categories", params={"page_size": 100})
    assert response.status_code == 200
    return str(next(item["id"] for item in response.json()["data"] if item["name"] == name))


def test_database_rejects_a_negative_financial_buffer(db_session: Session) -> None:
    db_session.add(
        FinancialAccount(
            workspace_id=DEFAULT_WORKSPACE_ID,
            name="Invalid buffer",
            account_type=FinancialAccountType.CHECKING,
            currency_code="EUR",
            financial_buffer_minor=-1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_finance_ledger_transfer_filters_import_safety_and_timeline(
    client: TestClient,
) -> None:
    checking = _account(client, "Main checking", opening=100_000, buffer=20_000)
    savings = _account(client, "Savings", opening=5_000)
    salary_id = _category_id(client, "Salary")
    food_id = _category_id(client, "Food")

    income = _data(
        client.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": checking["id"],
                "category_id": salary_id,
                "transaction_type": "income",
                "amount_minor": 250_000,
                "currency_code": "eur",
                "occurred_at": "2026-07-02T08:00:00+02:00",
                "payee": "Employer",
                "import_fingerprint": "payroll-2026-07",
            },
        ),
        201,
    )
    assert income["account_effects"] == [{"account_id": checking["id"], "effect_minor": 250_000}]
    duplicate = client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": checking["id"],
            "category_id": salary_id,
            "transaction_type": "income",
            "amount_minor": 250_000,
            "currency_code": "EUR",
            "occurred_at": "2026-07-02T08:00:00+02:00",
            "import_fingerprint": "payroll-2026-07",
        },
    )
    assert duplicate.status_code == 409

    _data(
        client.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": checking["id"],
                "category_id": food_id,
                "transaction_type": "expense",
                "amount_minor": 45_000,
                "currency_code": "EUR",
                "occurred_at": "2026-07-03T18:30:00+02:00",
                "payee": "Grocer",
            },
        ),
        201,
    )
    transfer = _data(
        client.post(
            "/api/v1/finance/transfers",
            json={
                "source_account_id": checking["id"],
                "destination_account_id": savings["id"],
                "amount_minor": 30_000,
                "currency_code": "EUR",
                "occurred_at": "2026-07-04T09:00:00+02:00",
                "payee": "Savings transfer",
            },
        ),
        201,
    )
    assert transfer["account_effects"] == [
        {"account_id": checking["id"], "effect_minor": -30_000},
        {"account_id": savings["id"], "effect_minor": 30_000},
    ]

    checking_after = _data(client.get(f"/api/v1/finance/accounts/{checking['id']}"))
    savings_after = _data(client.get(f"/api/v1/finance/accounts/{savings['id']}"))
    assert checking_after["balance_minor"] == 275_000
    assert savings_after["balance_minor"] == 35_000
    assert checking_after["below_financial_buffer"] is False

    ledger = _data(client.get(f"/api/v1/finance/accounts/{checking['id']}/ledger"))
    assert [entry["effect_minor"] for entry in ledger["entries"]] == [
        250_000,
        -45_000,
        -30_000,
    ]
    assert ledger["entries"][-1]["balance_after_minor"] == 275_000

    filtered = client.get(
        "/api/v1/finance/transactions",
        params={"type": "expense", "page_size": 1, "currency": "eur"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["meta"]["total_items"] == 1
    assert filtered.json()["data"][0]["payee"] == "Grocer"
    assert client.get("/api/v1/finance/accounts", params={"currency": "ZZZ"}).status_code == 422

    timeline = client.get(
        "/api/v1/timeline",
        params={"action": "transaction_transfer_created"},
    )
    assert timeline.status_code == 200
    assert timeline.json()["meta"]["total_items"] == 1


def test_planned_fulfillment_updates_the_ledger_once_and_revisions_conflict(
    client: TestClient,
) -> None:
    account = _account(client, "Daily", opening=50_000)
    food_id = _category_id(client, "Food")
    planned = _data(
        client.post(
            "/api/v1/finance/transactions/planned",
            json={
                "account_id": account["id"],
                "category_id": food_id,
                "transaction_type": "expense",
                "amount_minor": 8_000,
                "currency_code": "EUR",
                "planned_for": "2026-07-20T12:00:00+02:00",
                "payee": "Planned lunch",
                "is_committed": True,
            },
        ),
        201,
    )
    before = _data(client.get(f"/api/v1/finance/accounts/{account['id']}"))
    assert before["balance_minor"] == 50_000

    fulfilled = _data(
        client.post(
            f"/api/v1/finance/transactions/planned/{planned['id']}/fulfill",
            json={
                "revision": planned["revision"],
                "occurred_at": "2026-07-20T12:30:00+02:00",
            },
        )
    )
    assert fulfilled["planned"]["status"] == "fulfilled"
    assert fulfilled["planned"]["actual_transaction_id"] == fulfilled["actual"]["id"]
    after = _data(client.get(f"/api/v1/finance/accounts/{account['id']}"))
    assert after["balance_minor"] == 42_000

    repeated = client.post(
        f"/api/v1/finance/transactions/planned/{planned['id']}/fulfill",
        json={
            "revision": fulfilled["planned"]["revision"],
            "occurred_at": "2026-07-20T12:30:00+02:00",
        },
    )
    assert repeated.status_code == 409
    retained_actual = client.delete(
        f"/api/v1/finance/transactions/{fulfilled['actual']['id']}",
        params={"revision": fulfilled["actual"]["revision"]},
    )
    assert retained_actual.status_code == 409
    updated_account = _data(
        client.patch(
            f"/api/v1/finance/accounts/{account['id']}",
            json={"revision": account["revision"], "name": "Daily updated"},
        )
    )
    assert updated_account["revision"] == account["revision"] + 1
    stale = client.patch(
        f"/api/v1/finance/accounts/{account['id']}",
        json={"revision": account["revision"], "name": "Stale update"},
    )
    assert stale.status_code == 409
