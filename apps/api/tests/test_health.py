from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_service_status_and_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "LocalLife OS API"
    assert response.headers["X-Request-ID"]


def test_health_preserves_valid_caller_request_id(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "local-test-request"},
    )

    assert response.headers["X-Request-ID"] == "local-test-request"


def test_cors_allows_loopback_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_not_found_uses_structured_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]
