"""Tests for the health check and request-context middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "local"
    assert body["service"]


def test_health_sets_request_id_header(client: TestClient) -> None:
    response = client.get("/health")
    assert response.headers.get("X-Request-ID")


def test_request_id_is_echoed_when_provided(client: TestClient) -> None:
    provided = "test-correlation-id"
    response = client.get("/health", headers={"X-Request-ID": provided})
    assert response.headers.get("X-Request-ID") == provided


def test_openapi_is_available(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]
