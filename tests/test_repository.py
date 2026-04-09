"""Repository tests for incident deduplication behavior."""

from __future__ import annotations

from database.repository import IncidentRepository
from monitoring.models import utc_now_iso


def build_incident(incident_id: str) -> dict[str, object]:
    return {
        "incident_id": incident_id,
        "type": "pod_restart_loop",
        "severity": "critical",
        "service_affected": "cartservice",
        "pod": "cartservice-abc123-xyz",
        "detected_at": utc_now_iso(),
        "error_message": "Pod cartservice-abc123-xyz has restarted 5 times",
        "alert_name": "PodRestartLoop",
        "metrics_snapshot": {},
        "namespace": "default",
        "source": "prometheus",
        "status": "active",
    }


def test_recent_fingerprint_treats_simulated_incidents_as_open(tmp_path) -> None:
    repo = IncidentRepository(database_url=f"sqlite:///{(tmp_path / 'protocol_zero.db').as_posix()}")
    incident = build_incident("INC-TEST-001")

    repo.upsert_incident(incident, {"status": "investigating"})
    repo.save_state(incident["incident_id"], {"status": "simulated"})

    recent = repo.recent_fingerprint(repo.build_fingerprint(incident), window_minutes=10)

    assert recent is not None
    assert recent["incident_id"] == incident["incident_id"]
    assert recent["status"] == "simulated"


def test_recent_fingerprint_ignores_resolved_incidents(tmp_path) -> None:
    repo = IncidentRepository(database_url=f"sqlite:///{(tmp_path / 'protocol_zero.db').as_posix()}")
    incident = build_incident("INC-TEST-002")

    repo.upsert_incident(incident, {"status": "investigating"})
    repo.save_state(incident["incident_id"], {"status": "resolved"})

    recent = repo.recent_fingerprint(repo.build_fingerprint(incident), window_minutes=10)

    assert recent is None
