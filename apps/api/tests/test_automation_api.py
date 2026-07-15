from __future__ import annotations

from datetime import UTC, timedelta
from typing import Any
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.db.session import get_engine
from app.models import AutomationRule, AutomationTriggerType
from app.models.common import utc_now
from app.repositories.automation import AutomationRuleRepository
from app.services.automation import dispatch_automation_event
from app.services.automation_scheduler import RULE_JOB_PREFIX, reconcile_scheduler
from app.services.seed import DEFAULT_WORKSPACE_ID


def _data(response: Response, expected_status: int = 200) -> Any:
    assert response.status_code == expected_status, response.text
    return response.json()["data"] if "data" in response.json() else response.json()


def _notification_rule(client: TestClient) -> dict[str, Any]:
    return _data(
        client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Large transaction notice",
                "description": "Notify locally for larger ledger entries.",
                "trigger": {
                    "type": "transaction_created",
                    "conditions": [
                        {
                            "field": "amount_minor",
                            "operator": "greater_than_or_equal",
                            "value": 1000,
                        }
                    ],
                },
                "action": {
                    "type": "create_notification",
                    "title": "Review this transaction",
                    "body": "A larger local transaction was recorded.",
                },
            },
        ),
        201,
    )


def test_rule_crud_preview_event_execution_logs_and_idempotency(client: TestClient) -> None:
    rule = _notification_rule(client)
    assert rule["execution_count"] == 0

    preview = _data(
        client.post(
            f"/api/v1/automation/rules/{rule['id']}/test",
            json={"context": {"amount_minor": 1250}},
        )
    )
    assert preview["matched"] is True
    assert preview["writes_performed"] is False
    assert _data(client.get("/api/v1/automation/notifications")) == []

    account = _data(
        client.post(
            "/api/v1/finance/accounts",
            json={
                "name": "Automation checking",
                "account_type": "checking",
                "currency_code": "EUR",
                "opening_balance_minor": 0,
            },
        ),
        201,
    )
    transaction = _data(
        client.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount_minor": 1250,
                "currency_code": "EUR",
                "occurred_at": "2026-07-15T10:00:00+02:00",
                "payee": "Local shop",
            },
        ),
        201,
    )
    notifications = _data(client.get("/api/v1/automation/notifications"))
    assert len(notifications) == 1
    assert notifications[0]["title"] == "Review this transaction"
    executions = client.get("/api/v1/automation/executions")
    assert executions.status_code == 200
    assert executions.json()["meta"]["total_items"] == 1
    assert executions.json()["data"][0]["status"] == "succeeded"

    with Session(get_engine()) as session:
        stored = AutomationRuleRepository(session).get_active(
            DEFAULT_WORKSPACE_ID, UUID(rule["id"])
        )
        assert stored is not None
        context = {
            "entity_type": "transaction",
            "entity_id": transaction["id"],
            "amount_minor": 1250,
        }
        first = dispatch_automation_event(
            session,
            AutomationTriggerType.TRANSACTION_CREATED,
            context=context,
            source_key="manual-idempotency-key",
        )
        second = dispatch_automation_event(
            session,
            AutomationTriggerType.TRANSACTION_CREATED,
            context=context,
            source_key="manual-idempotency-key",
        )
        assert first[0].id == second[0].id

    assert len(_data(client.get("/api/v1/automation/notifications"))) == 2
    executions = client.get("/api/v1/automation/executions")
    assert executions.json()["meta"]["total_items"] == 2

    updated = _data(
        client.patch(
            f"/api/v1/automation/rules/{rule['id']}",
            json={"revision": rule["revision"], "enabled": False},
        )
    )
    assert updated["enabled"] is False
    conflict = client.patch(
        f"/api/v1/automation/rules/{rule['id']}",
        json={"revision": rule["revision"], "name": "stale"},
    )
    assert conflict.status_code == 409
    assert (
        client.delete(
            f"/api/v1/automation/rules/{rule['id']}",
            params={"revision": updated["revision"]},
        ).status_code
        == 200
    )


def test_rule_validation_and_scheduler_rebuild_from_database(client: TestClient) -> None:
    invalid = client.post(
        "/api/v1/automation/rules",
        json={
            "name": "Unsafe field",
            "trigger": {
                "type": "task_overdue",
                "conditions": [{"field": "python_code", "operator": "equals", "value": "x"}],
            },
            "action": {"type": "create_note", "title": "No"},
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "automation_condition_field"

    recurring = _data(
        client.post(
            "/api/v1/automation/rules",
            json={
                "name": "Weekly local backup reminder",
                "trigger": {
                    "type": "recurring_schedule",
                    "schedule": {
                        "frequency": "weekly",
                        "timezone": "Europe/Rome",
                        "local_time": "18:30:00",
                        "weekdays": [4],
                    },
                },
                "action": {
                    "type": "request_local_backup_reminder",
                    "title": "Create a local backup",
                },
            },
        ),
        201,
    )
    assert recurring["next_run_at"] is not None

    scheduler = BackgroundScheduler(timezone=UTC)
    try:
        with Session(get_engine()) as session:
            scheduled = reconcile_scheduler(session, scheduler, run_catch_up=False)
        assert scheduled == [UUID(recurring["id"])]
        assert scheduler.get_job(f"{RULE_JOB_PREFIX}{recurring['id']}") is not None
    finally:
        scheduler.shutdown(wait=False) if scheduler.running else None

    with Session(get_engine()) as session:
        stored = session.get(AutomationRule, UUID(recurring["id"]))
        assert stored is not None
        assert stored.next_run_at is not None
        stored.next_run_at = utc_now() - timedelta(minutes=1)
        session.add(stored)
        session.commit()
        reconcile_scheduler(session, scheduler, run_catch_up=True)
        reconcile_scheduler(session, scheduler, run_catch_up=True)

    catch_up_executions = client.get(
        "/api/v1/automation/executions", params={"rule_id": recurring["id"]}
    )
    assert catch_up_executions.status_code == 200
    assert catch_up_executions.json()["meta"]["total_items"] == 1
    assert len(_data(client.get("/api/v1/automation/notifications"))) == 1

    scheduler_status = _data(client.get("/api/v1/automation/scheduler"))
    assert scheduler_status == {
        "running": False,
        "scheduled_rule_ids": [],
        "next_wakeup_at": None,
    }
