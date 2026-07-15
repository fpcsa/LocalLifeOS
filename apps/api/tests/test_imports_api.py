from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from httpx import Response


def _data(response: Response, expected_status: int = 200) -> Any:
    assert response.status_code == expected_status, response.text
    return response.json()["data"]


def _account(client: TestClient, name: str = "Import account") -> dict[str, Any]:
    return _data(
        client.post(
            "/api/v1/finance/accounts",
            json={
                "name": name,
                "account_type": "checking",
                "currency_code": "EUR",
                "opening_balance_minor": 0,
            },
        ),
        201,
    )


def test_calendar_import_preview_apply_change_export_and_idempotency(
    client: TestClient,
) -> None:
    initial = b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//LocalLife test//EN\r
BEGIN:VEVENT\r
UID:weekly-focus@example.local\r
DTSTAMP:20260715T080000Z\r
DTSTART;TZID=Europe/Rome:20260720T090000\r
DTEND;TZID=Europe/Rome:20260720T100000\r
RRULE:FREQ=WEEKLY;COUNT=3\r
SUMMARY:Weekly focus\r
LOCATION:Home office\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:holiday@example.local\r
DTSTAMP:20260715T080000Z\r
DTSTART;VALUE=DATE:20260815\r
DTEND;VALUE=DATE:20260816\r
SUMMARY:Holiday\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:invalid@example.local\r
DTSTART:20260720T120000Z\r
DTEND:20260720T130000Z\r
END:VEVENT\r
END:VCALENDAR\r
"""
    preview = _data(
        client.post(
            "/api/v1/imports/calendar/preview",
            files={"file": ("calendar.ics", initial, "text/calendar")},
        ),
        201,
    )
    assert preview["batch"]["new_count"] == 2
    assert preview["batch"]["invalid_count"] == 1
    weekly = next(row for row in preview["rows"] if row["raw_data"]["summary"] == "Weekly focus")
    assert weekly["normalized_data"]["timezone"] == "Europe/Rome"
    assert weekly["normalized_data"]["recurrence_rrule"] == "FREQ=WEEKLY;COUNT=3"

    applied = _data(
        client.post(
            f"/api/v1/imports/calendar/{preview['batch']['id']}/apply",
            json={},
        )
    )
    assert applied["status"] == "applied"
    assert applied["imported_count"] == 2
    reapplied = _data(
        client.post(
            f"/api/v1/imports/calendar/{preview['batch']['id']}/apply",
            json={},
        )
    )
    assert reapplied["imported_count"] == 2

    duplicate_source = initial.replace(
        b"PRODID:-//LocalLife test//EN", b"PRODID:-//A different source//EN"
    )
    duplicate = _data(
        client.post(
            "/api/v1/imports/calendar/preview",
            files={"file": ("duplicate.ics", duplicate_source, "text/calendar")},
        ),
        201,
    )
    assert duplicate["batch"]["duplicate_count"] == 2
    assert all(not row["included"] for row in duplicate["rows"] if row["status"] == "duplicate")

    changed_source = duplicate_source.replace(b"Weekly focus", b"Weekly focus updated")
    changed = _data(
        client.post(
            "/api/v1/imports/calendar/preview",
            files={"file": ("changed.ics", changed_source, "text/calendar")},
        ),
        201,
    )
    assert changed["batch"]["changed_count"] == 1
    assert changed["batch"]["duplicate_count"] == 1
    _data(
        client.post(
            f"/api/v1/imports/calendar/{changed['batch']['id']}/apply",
            json={},
        )
    )

    events = client.get(
        "/api/v1/calendar/events",
        params={
            "start": "2026-07-01T00:00:00Z",
            "end": "2026-09-01T00:00:00Z",
        },
    )
    assert events.status_code == 200, events.text
    assert {item["title"] for item in events.json()["data"]} >= {
        "Weekly focus updated",
        "Holiday",
    }
    exported = client.get("/api/v1/imports/calendar/export.ics")
    assert exported.status_code == 200
    assert b"BEGIN:VCALENDAR" in exported.content
    assert b"weekly-focus@example.local" in exported.content
    assert b"RRULE:FREQ=WEEKLY;COUNT=3" in exported.content

    history = client.get("/api/v1/imports", params={"kind": "calendar_ics"})
    assert history.status_code == 200
    assert history.json()["meta"]["total_items"] == 3


def test_csv_mapping_profiles_normalization_duplicates_selection_and_safe_review(
    client: TestClient,
) -> None:
    account = _account(client)
    content = (
        "Date;Description;Debit;Credit;Currency;Reference\n"
        "15/07/2026;Grocer;12,34;;EUR;bank-1\n"
        '16/07/2026;=HYPERLINK("bad");;1000,00;EUR;bank-2\n'
        "not-a-date;Broken;4,00;;EUR;bank-3\n"
    ).encode("cp1252")
    preview = _data(
        client.post(
            "/api/v1/imports/csv/preview",
            files={"file": ("bank.csv", content, "text/csv")},
        ),
        201,
    )
    assert preview["batch"]["detected_delimiter"] == ";"
    assert preview["batch"]["detected_encoding"] in {"utf-8-sig", "utf-8", "cp1252"}
    assert preview["columns"] == [
        "Date",
        "Description",
        "Debit",
        "Credit",
        "Currency",
        "Reference",
    ]

    mapping = {
        "columns": {
            "date": "Date",
            "description": "Description",
            "debit": "Debit",
            "credit": "Credit",
            "currency": "Currency",
            "external_id": "Reference",
        },
        "date_format": "%d/%m/%Y",
        "decimal_separator": ",",
        "default_account_id": account["id"],
        "save_profile": True,
        "profile_name": "My semicolon bank",
    }
    mapped = _data(client.post(f"/api/v1/imports/csv/{preview['batch']['id']}/map", json=mapping))
    assert mapped["batch"]["new_count"] == 2
    assert mapped["batch"]["invalid_count"] == 1
    assert mapped["rows"][0]["normalized_data"]["amount_minor"] == 1234
    assert mapped["rows"][0]["normalized_data"]["transaction_type"] == "expense"
    assert mapped["rows"][1]["normalized_data"]["amount_minor"] == 100000
    assert mapped["rows"][1]["normalized_data"]["transaction_type"] == "income"

    excluded = mapped["rows"][1]
    changed = _data(
        client.patch(
            f"/api/v1/imports/rows/{excluded['id']}",
            json={"revision": excluded["revision"], "included": False},
        )
    )
    assert changed["included"] is False
    assert (
        client.patch(
            f"/api/v1/imports/rows/{excluded['id']}",
            json={"revision": excluded["revision"], "included": True},
        ).status_code
        == 409
    )

    applied = _data(client.post(f"/api/v1/imports/csv/{preview['batch']['id']}/apply", json={}))
    assert applied["imported_count"] == 1
    assert (
        _data(client.post(f"/api/v1/imports/csv/{preview['batch']['id']}/apply", json={}))[
            "imported_count"
        ]
        == 1
    )

    profiles = _data(client.get("/api/v1/imports/mapping-profiles"))
    assert [item["name"] for item in profiles] == ["My semicolon bank"]

    review = client.get(f"/api/v1/imports/{preview['batch']['id']}/rows.csv")
    assert review.status_code == 200
    assert b"'=HYPERLINK" in review.content

    duplicate_content = content.replace(b"bank-3", b"bank-3-changed")
    duplicate_preview = _data(
        client.post(
            "/api/v1/imports/csv/preview",
            files={"file": ("again.csv", duplicate_content, "text/csv")},
        ),
        201,
    )
    duplicate_mapping = {**mapping, "save_profile": False, "profile_name": None}
    duplicate_mapped = _data(
        client.post(
            f"/api/v1/imports/csv/{duplicate_preview['batch']['id']}/map",
            json=duplicate_mapping,
        )
    )
    assert duplicate_mapped["batch"]["duplicate_count"] >= 1

    unsafe = client.post(
        "/api/v1/imports/csv/preview",
        files={"file": ("../escape.csv", b"a,b\n1,2", "text/csv")},
    )
    assert unsafe.status_code == 422
