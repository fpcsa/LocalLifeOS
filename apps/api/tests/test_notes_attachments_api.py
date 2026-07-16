from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.core.exceptions import DomainValidationError
from app.db.session import get_engine
from app.main import create_app
from app.services.attachments import resolve_attachment_path
from fastapi.testclient import TestClient


def _create_note(
    client: TestClient,
    title: str,
    markdown: str,
    **values: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/notes",
        json={"title": title, "markdown": markdown, **values},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_note_search_backlinks_links_delete_and_timeline(client: TestClient) -> None:
    source = _create_note(
        client,
        "Architecture",
        "The uncommon zephyrtoken appears in this design.",
        daily_note_date="2026-07-15",
    )
    target = _create_note(client, "Decisions", "Persistent local decisions.")

    duplicate_daily = client.post(
        "/api/v1/notes",
        json={"title": "Duplicate", "daily_note_date": "2026-07-15"},
    )
    assert duplicate_daily.status_code == 409
    assert duplicate_daily.json()["error"]["code"] == "duplicate_daily_note"

    search = client.get("/api/v1/notes", params={"q": "zephyrtoken", "sort": "relevance"})
    assert search.status_code == 200, search.text
    assert [note["id"] for note in search.json()["data"]] == [source["id"]]

    link_response = client.post(
        f"/api/v1/notes/{source['id']}/links",
        json={"target_note_id": target["id"], "label": "explains"},
    )
    assert link_response.status_code == 201, link_response.text
    link = link_response.json()["data"]

    target_with_backlink = client.get(f"/api/v1/notes/{target['id']}").json()["data"]
    assert [item["source_note_id"] for item in target_with_backlink["backlinks"]] == [source["id"]]

    removed = client.delete(f"/api/v1/notes/{source['id']}/links/{link['id']}")
    assert removed.status_code == 200
    assert client.get(f"/api/v1/notes/{target['id']}").json()["data"]["backlinks"] == []

    updated = client.patch(
        f"/api/v1/notes/{source['id']}",
        json={
            "revision": source["revision"],
            "markdown": "The replacement nebularesult is now indexed.",
        },
    )
    assert updated.status_code == 200, updated.text
    assert client.get("/api/v1/notes", params={"q": "zephyrtoken"}).json()["data"] == []
    assert (
        client.get("/api/v1/notes", params={"q": "nebularesult"}).json()["data"][0]["id"]
        == source["id"]
    )

    recreated = client.post(
        f"/api/v1/notes/{source['id']}/links",
        json={"target_note_id": target["id"]},
    )
    assert recreated.status_code == 201
    deleted = client.delete(
        f"/api/v1/notes/{target['id']}",
        params={"revision": target["revision"]},
    )
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/notes/{source['id']}").json()["data"]["links"] == []

    timeline = client.get(
        "/api/v1/timeline",
        params={"entity_type": "note", "entity_id": source["id"], "page_size": 100},
    )
    assert timeline.status_code == 200
    actions = {item["action"] for item in timeline.json()["data"]}
    assert {"note_created", "note_updated", "note_link_added", "note_link_removed"} <= actions


def test_attachment_upload_download_validation_and_delete(
    client: TestClient,
    database_path: Path,
) -> None:
    note = _create_note(client, "Files", "Local files only.")
    content = b"local attachment bytes\n"
    upload = client.post(
        "/api/v1/attachments",
        data={"entity_type": "note", "entity_id": note["id"]},
        files={"file": ("evidence.txt", content, "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    attachment = upload.json()["data"]
    assert attachment["size_bytes"] == len(content)
    assert attachment["sha256"] == hashlib.sha256(content).hexdigest()
    assert attachment["entity_type"] == "note"

    listed = client.get(
        "/api/v1/attachments",
        params={"entity_type": "note", "entity_id": note["id"]},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]] == [attachment["id"]]

    download = client.get(f"/api/v1/attachments/{attachment['id']}/download")
    assert download.status_code == 200
    assert download.content == content
    assert "evidence.txt" in download.headers["content-disposition"]

    unsafe = client.post(
        "/api/v1/attachments",
        data={"entity_type": "note", "entity_id": note["id"]},
        files={"file": ("../escape.txt", b"no", "text/plain")},
    )
    assert unsafe.status_code == 422
    assert unsafe.json()["error"]["code"] == "invalid_filename"
    with pytest.raises(DomainValidationError, match="outside"):
        resolve_attachment_path("../escape.txt")
    assert not (database_path.parent.parent / "escape.txt").exists()

    note_delete = client.delete(
        f"/api/v1/notes/{note['id']}",
        params={"revision": note["revision"]},
    )
    assert note_delete.status_code == 200
    retained = client.get(f"/api/v1/attachments/{attachment['id']}/download")
    assert retained.status_code == 200
    assert retained.content == content

    deleted = client.delete(
        f"/api/v1/attachments/{attachment['id']}",
        params={"revision": attachment["revision"]},
    )
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/attachments/{attachment['id']}/download").status_code == 404
    attachment_root = get_settings().attachments_dir
    assert attachment_root is not None
    assert not [path for path in attachment_root.rglob("*") if path.is_file()]


def test_attachment_size_limit_cleans_partial_files(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALLIFE_MAX_ATTACHMENT_BYTES", "4")
    get_settings.cache_clear()
    get_engine.cache_clear()
    with TestClient(create_app()) as client:
        note = _create_note(client, "Limits", "Small files.")
        response = client.post(
            "/api/v1/attachments",
            data={"entity_type": "note", "entity_id": note["id"]},
            files={"file": ("large.bin", b"12345", "application/octet-stream")},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "attachment_too_large"
        attachment_root = get_settings().attachments_dir
        assert attachment_root is not None
        assert not [path for path in attachment_root.rglob("*") if path.is_file()]
