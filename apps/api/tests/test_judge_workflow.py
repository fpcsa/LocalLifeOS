from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db.session import get_engine
from app.main import create_app
from app.services.backups import restore_backup
from fastapi.testclient import TestClient
from httpx import Response


def _data(response: Response, expected_status: int = 200) -> Any:
    assert response.status_code == expected_status, response.text
    return response.json()["data"]


def test_complete_judge_workflow_from_empty_imports_through_restore(
    database_path: Path,
) -> None:
    del database_path
    root = Path(__file__).resolve().parents[3]
    calendar_source = (root / "data" / "demo" / "calendar.ics").read_bytes()
    bank_source = (root / "data" / "demo" / "bank-transactions.csv").read_bytes()
    password = "synthetic judge backup passphrase"

    with TestClient(create_app()) as client:
        # 1. Begin with an empty domain workspace.
        assert client.get("/api/v1/projects").json()["meta"]["total_items"] == 0

        # 2. Import a local ICS file through preview and explicit apply.
        calendar_preview = _data(
            client.post(
                "/api/v1/imports/calendar/preview",
                files={"file": ("calendar.ics", calendar_source, "text/calendar")},
            ),
            201,
        )
        calendar_batch = _data(
            client.post(
                f"/api/v1/imports/calendar/{calendar_preview['batch']['id']}/apply",
                json={},
            )
        )
        assert calendar_batch["imported_count"] == 2

        # 3. Import income and expenses from the bundled bank CSV.
        account = _data(
            client.post(
                "/api/v1/finance/accounts",
                json={
                    "name": "Judge checking",
                    "account_type": "checking",
                    "currency_code": "EUR",
                    "opening_balance_minor": 300_000,
                    "financial_buffer_minor": 100_000,
                },
            ),
            201,
        )
        csv_preview = _data(
            client.post(
                "/api/v1/imports/csv/preview",
                files={"file": ("bank.csv", bank_source, "text/csv")},
            ),
            201,
        )
        mapped = _data(
            client.post(
                f"/api/v1/imports/csv/{csv_preview['batch']['id']}/map",
                json={
                    "columns": {
                        "date": "Date",
                        "description": "Description",
                        "amount": "Amount",
                        "currency": "Currency",
                        "external_id": "External ID",
                    },
                    "date_format": "%Y-%m-%d",
                    "decimal_separator": ".",
                    "default_account_id": account["id"],
                },
            )
        )
        assert mapped["batch"]["new_count"] == 3
        bank_batch = _data(
            client.post(f"/api/v1/imports/csv/{csv_preview['batch']['id']}/apply", json={})
        )
        assert bank_batch["imported_count"] == 3
        ledger = client.get("/api/v1/finance/transactions", params={"page_size": 100}).json()[
            "data"
        ]
        assert {row["transaction_type"] for row in ledger} == {"income", "expense"}

        # 4. Create a linked project and task.
        project = _data(
            client.post(
                "/api/v1/projects",
                json={"name": "Judge workflow project", "target_end_date": "2026-07-31"},
            ),
            201,
        )
        task = _data(
            client.post(
                "/api/v1/tasks",
                json={
                    "title": "Prepare judge walkthrough",
                    "project_id": project["id"],
                    "priority": "high",
                    "estimated_duration_minutes": 60,
                    "due_at": "2026-07-23T17:00:00Z",
                },
            ),
            201,
        )

        # 5. Create notes and prove backlink generation.
        note = _data(
            client.post(
                "/api/v1/notes",
                json={"title": "Judge decisions", "markdown": "Offline-first evidence."},
            ),
            201,
        )
        evidence = _data(
            client.post(
                "/api/v1/notes",
                json={"title": "Judge evidence", "markdown": "Backup and restore proof."},
            ),
            201,
        )
        _data(
            client.post(
                f"/api/v1/notes/{note['id']}/links",
                json={"target_note_id": evidence["id"], "label": "supports"},
            ),
            201,
        )
        assert (
            _data(client.get(f"/api/v1/notes/{evidence['id']}"))["backlinks"][0]["source_note_id"]
            == note["id"]
        )

        # 6–9. Add a commitment, link existing records, and assess impact.
        commitment = _data(
            client.post(
                "/api/v1/commitments",
                json={
                    "title": "Judge-ready release",
                    "status": "planned",
                    "target_end_at": "2026-07-24T17:00:00Z",
                    "time_capacity_requirement_minutes": 60,
                },
            ),
            201,
        )
        for entity_type, entity_id in (
            ("project", project["id"]),
            ("task", task["id"]),
            ("note", note["id"]),
        ):
            _data(
                client.post(
                    f"/api/v1/commitments/{commitment['id']}/links",
                    json={"entity_type": entity_type, "entity_id": entity_id},
                ),
                201,
            )
        assessment = _data(client.get(f"/api/v1/commitments/{commitment['id']}/assessment"))
        assert assessment["impact"]["time"]["time_capacity_requirement_minutes"] >= 60

        # 10. Load canonical conflict and shortfall evidence, then query the real services.
        demo = _data(client.post("/api/v1/demo/load"))
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
        assert len(conflicts) >= demo["conflict_count"]

        # 11. Preview and atomically apply a bounded schedule.
        preview = _data(
            client.post(
                "/api/v1/scheduling/preview",
                json={
                    "task_ids": [task["id"]],
                    "planning_start_at": "2026-07-23T09:00:00Z",
                    "planning_end_at": "2026-07-23T17:00:00Z",
                },
            ),
            201,
        )
        assert preview["solver_status"] in {"optimal", "feasible"}
        assert len(preview["placements"]) == 1
        _data(client.post("/api/v1/scheduling/apply", json={"preview_id": preview["preview_id"]}))

        # 12. Compare two what-if overlays and accept an exact reviewed plan.
        current_task = _data(client.get(f"/api/v1/tasks/{task['id']}"))
        scenario_ids: list[str] = []
        for name, estimate in (("Judge fast path", 45), ("Judge careful path", 90)):
            scenario = _data(client.post("/api/v1/scenarios", json={"name": name}), 201)
            scenario_ids.append(scenario["id"])
            _data(
                client.post(
                    f"/api/v1/scenarios/{scenario['id']}/changes",
                    json={
                        "entity_type": "task",
                        "entity_id": task["id"],
                        "operation": "update",
                        "changes": {"estimated_duration_minutes": estimate},
                    },
                ),
                201,
            )
        comparison = _data(
            client.post("/api/v1/scenarios/compare", json={"scenario_ids": scenario_ids})
        )
        assert len(comparison["previews"]) == 2
        accepted_preview = comparison["previews"][0]
        _data(
            client.post(
                f"/api/v1/scenarios/{scenario_ids[0]}/accept",
                json={
                    "revision": accepted_preview["scenario"]["revision"],
                    "preview_fingerprint": accepted_preview["preview_fingerprint"],
                },
            )
        )
        assert (
            _data(client.get(f"/api/v1/tasks/{task['id']}"))["estimated_duration_minutes"]
            != current_task["estimated_duration_minutes"]
        )

        # 13–14. Create an encrypted backup, clear the workspace, and restore it cleanly.
        backup = _data(
            client.post(
                "/api/v1/privacy/backups",
                json={"password": password, "label": "judge-workflow"},
            ),
            201,
        )["backup"]
        assert backup["encrypted"] is True
        backup_path = Path(backup["path"])
        _data(
            client.post(
                "/api/v1/privacy/delete-all",
                json={"confirmation": "DELETE ALL LOCAL DATA", "include_backups": False},
            )
        )
        assert client.get("/api/v1/projects").json()["meta"]["total_items"] == 0

    get_engine().dispose()
    restored = restore_backup(backup_path, password=password)
    assert restored.manifest.encrypted is True
    with TestClient(create_app()) as restored_client:
        restored_project = _data(restored_client.get(f"/api/v1/projects/{project['id']}"))
        assert restored_project["name"] == "Judge workflow project"
        assert (
            _data(restored_client.get("/api/v1/privacy/status"))["network_mode"] == "loopback-only"
        )
