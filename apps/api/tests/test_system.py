from __future__ import annotations

from fastapi.testclient import TestClient


def test_system_info_reports_local_runtime_guarantees(client: TestClient) -> None:
    response = client.get("/api/v1/system/info")

    assert response.status_code == 200
    assert response.json() == {
        "application": "LocalLife OS",
        "version": "0.1.0",
        "environment": "test",
        "storage": "sqlite",
        "timezone": "UTC",
        "telemetry_enabled": False,
        "external_requests_enabled": False,
    }
