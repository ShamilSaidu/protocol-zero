"""Smoke tests for the public FastAPI demo surface."""

from __future__ import annotations

from fastapi.testclient import TestClient

import main


class StubRuntime:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def health(self) -> dict:
        return {
            "status": "healthy",
            "namespace": "default",
            "database_url": "sqlite:///memory",
            "dry_run_mode": True,
            "dependencies": {
                "database_url": "sqlite:///memory",
                "prometheus": {"configured": True, "available": True, "base_url": "http://localhost:9090"},
                "redis": {"configured": True, "available": True, "backend": "redis"},
                "loki": {"configured": True, "available": True, "base_url": "http://localhost:3100"},
            },
        }

    def stats(self) -> dict:
        return {
            "total_incidents": 1,
            "active": 1,
            "resolved": 0,
            "database_url": "sqlite:///memory",
            "dry_run_mode": True,
            "background_detector": False,
            "prometheus": {"configured": True, "available": True, "base_url": "http://localhost:9090"},
            "redis": {"configured": True, "available": True, "backend": "redis"},
            "loki": {"configured": True, "available": True, "base_url": "http://localhost:3100"},
        }

    def list_events(self, limit: int = 25) -> list[dict]:
        return [{"timestamp": "2026-04-07T10:00:00+00:00", "type": "demo", "message": "Runtime ready.", "details": {}}]

    def query_logs(self, service: str | None = None, limit: int = 100, since_minutes: int = 15) -> dict:
        return {
            "query": '{namespace="default",app="cartservice"}' if service else '{namespace="default"}',
            "logs": [{"timestamp_ns": "100", "labels": {"app": service or "cartservice"}, "line": "hello from loki"}],
            "available": True,
        }

    def list_incidents(self, limit: int = 50) -> list[dict]:
        return [{"incident_id": "INC-TEST-001", "service_affected": "cartservice", "incident_type": "pod_restart_loop", "status": "simulated"}]

    def get_incident(self, incident_id: str) -> dict | None:
        return {"incident_id": incident_id, "state": {"status": "simulated"}}

    async def trigger_incident(self, service: str, incident_type: str, severity: str, error_message: str | None = None) -> dict:
        return {"incident_id": "INC-TEST-001", "payload": {"service_affected": service, "type": incident_type}, "state": {"status": "simulated"}}

    async def run_detection_cycle(self, auto_process: bool = True) -> dict:
        return {"detected": 1, "processed": 1 if auto_process else 0, "skipped": 0, "incidents": []}

    async def reprocess_incident(self, incident_id: str) -> dict | None:
        return {"incident_id": incident_id, "state": {"status": "simulated"}}

    def get_postmortem(self, incident_id: str) -> dict | None:
        return {"path": f"post_mortems/{incident_id}.md", "content": "# Demo"}


def test_api_smoke_surface(monkeypatch) -> None:
    monkeypatch.setattr(main, "RUNTIME", StubRuntime())

    with TestClient(main.app) as client:
        health = client.get("/health")
        stats = client.get("/api/stats")
        events = client.get("/api/events")
        logs = client.get("/api/logs", params={"service": "cartservice"})
        incidents = client.get("/api/incidents")
        trigger = client.post(
            "/api/incidents/trigger",
            json={"service": "cartservice", "incident_type": "pod_restart_loop", "severity": "critical"},
        )

    assert health.status_code == 200
    assert health.json()["dependencies"]["prometheus"]["available"] is True
    assert stats.status_code == 200
    assert stats.json()["redis"]["backend"] == "redis"
    assert events.status_code == 200
    assert events.json()["events"][0]["type"] == "demo"
    assert logs.status_code == 200
    assert logs.json()["logs"][0]["line"] == "hello from loki"
    assert incidents.status_code == 200
    assert incidents.json()["incidents"][0]["incident_id"] == "INC-TEST-001"
    assert trigger.status_code == 200
    assert trigger.json()["state"]["status"] == "simulated"
