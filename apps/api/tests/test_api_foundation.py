from __future__ import annotations

from fastapi.testclient import TestClient


def test_workspace_and_preferences_endpoints_support_revision_updates(
    client: TestClient,
) -> None:
    workspace_response = client.get("/api/v1/workspaces/current")
    assert workspace_response.status_code == 200
    workspace = workspace_response.json()["data"]
    assert workspace["name"] == "Local workspace"

    patch_response = client.patch(
        "/api/v1/workspaces/current",
        json={"name": "My local workspace", "revision": workspace["revision"]},
    )
    assert patch_response.status_code == 200
    updated_workspace = patch_response.json()["data"]
    assert updated_workspace["name"] == "My local workspace"
    assert updated_workspace["revision"] == workspace["revision"] + 1

    stale_response = client.patch(
        "/api/v1/workspaces/current",
        json={"name": "Stale", "revision": workspace["revision"]},
    )
    assert stale_response.status_code == 409
    assert stale_response.json()["error"]["code"] == "revision_conflict"

    preferences_response = client.get("/api/v1/preferences")
    preferences = preferences_response.json()["data"]
    update_preferences = client.patch(
        "/api/v1/preferences",
        json={"currency_code": "USD", "revision": preferences["revision"]},
    )
    assert update_preferences.status_code == 200
    assert update_preferences.json()["data"]["currency_code"] == "USD"


def test_tag_endpoints_filter_sort_paginate_and_soft_delete(client: TestClient) -> None:
    created_ids: list[str] = []
    for name in ("Travel", "Focus", "Finance"):
        response = client.post("/api/v1/tags", json={"name": name})
        assert response.status_code == 201
        created_ids.append(response.json()["data"]["id"])

    filtered = client.get(
        "/api/v1/tags",
        params={"q": "f", "sort": "name", "order": "asc", "page_size": 1},
    )
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["meta"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 2,
        "total_pages": 2,
    }
    assert payload["data"][0]["name"] == "Finance"

    focus = client.get("/api/v1/tags", params={"q": "Focus"}).json()["data"][0]
    deleted = client.delete(
        f"/api/v1/tags/{focus['id']}",
        params={"revision": focus["revision"]},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"id": focus["id"], "deleted": True}

    remaining_ids = {item["id"] for item in client.get("/api/v1/tags").json()["data"]}
    assert focus["id"] not in remaining_ids
    assert set(created_ids) - {focus["id"]} <= remaining_ids


def test_timeline_pagination_meta_enums_and_openapi(client: TestClient) -> None:
    for name in ("One", "Two", "Three"):
        assert client.post("/api/v1/tags", json={"name": name}).status_code == 201

    timeline = client.get("/api/v1/timeline", params={"page": 2, "page_size": 2})
    assert timeline.status_code == 200
    payload = timeline.json()
    assert payload["meta"]["page"] == 2
    assert payload["meta"]["page_size"] == 2
    assert payload["meta"]["total_items"] == 3
    assert payload["meta"]["total_pages"] == 2
    assert len(payload["data"]) == 1

    enums = client.get("/api/v1/meta/enums")
    assert enums.status_code == 200
    assert enums.json()["data"]["enums"]["transaction_type"] == [
        "income",
        "expense",
        "transfer",
    ]

    openapi = client.get("/openapi.json").json()
    assert "WorkspaceResponse" in openapi["components"]["schemas"]
    assert "/api/v1/timeline" in openapi["paths"]
