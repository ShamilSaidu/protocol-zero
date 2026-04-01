"""End-to-end dry-run tests for the Protocol Zero orchestration flow."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.graph import ProtocolZeroOrchestrator


class FakeKubectl:
    def available(self):
        return True

    def get_pods(self, service: str):
        return [{"metadata": {"name": f"{service}-abc123-xyz"}}]

    def get_deployment(self, service: str):
        return {"status": {"availableReplicas": 0, "unavailableReplicas": 1}}

    def get_recent_events(self, service: str | None = None, limit: int = 12):
        return [
            "BackOff: Back-off restarting failed container",
            "Failed: Error syncing pod",
        ]

    def get_logs(self, pod: str, tail_lines: int = 120):
        return "panic: downstream connection refused"

    def delete_pod(self, pod: str):
        return {"returncode": 0, "stdout": f"deleted {pod}", "stderr": ""}

    def rollout_restart(self, deployment: str):
        return {"returncode": 0, "stdout": f"restarted {deployment}", "stderr": ""}

    def scale_deployment(self, deployment: str, replicas: int):
        return {"returncode": 0, "stdout": f"scaled {deployment} to {replicas}", "stderr": ""}


@pytest.mark.asyncio
async def test_full_incident_lifecycle_generates_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DRY_RUN_MODE", "true")
    monkeypatch.setenv("ALLOW_GITHUB_WRITE", "false")

    orchestrator = ProtocolZeroOrchestrator(namespace="default")
    fake = FakeKubectl()
    orchestrator.kubectl = fake
    orchestrator.investigation_agent.kubectl = fake
    orchestrator.devops_agent.kubectl = fake
    orchestrator.remediation.kubectl = fake
    orchestrator.code_fix.output_dir = tmp_path / "codefixes"
    orchestrator.code_fix.output_dir.mkdir(parents=True, exist_ok=True)
    orchestrator.post_mortem.output_dir = tmp_path / "postmortems"
    orchestrator.post_mortem.output_dir.mkdir(parents=True, exist_ok=True)

    incident = {
        "incident_id": "INC-TEST-E2E-001",
        "type": "pod_restart_loop",
        "severity": "critical",
        "service_affected": "cartservice",
        "pod": "cartservice-abc123-xyz",
        "detected_at": "2026-03-30T10:00:00Z",
        "error_message": "Pod cartservice-abc123-xyz has restarted 5 times",
        "alert_name": "PodRestartLoop",
        "metrics_snapshot": {
            "pod_restarts": {"cartservice-abc123-xyz": 5},
            "cpu_usage_pct": {"cartservice-abc123-xyz": 12.4},
            "memory_usage_mb": {"cartservice-abc123-xyz": 220.0},
            "unavailable_replicas": {"cartservice": 1},
        },
        "namespace": "default",
        "source": "test",
        "status": "active",
    }

    final_state = await orchestrator.handle_incident(incident)

    assert final_state["current_step"] == "post_mortem_generated"
    assert len(final_state["investigation_findings"]) == 3
    assert final_state["selected_hypothesis"]["root_cause"]
    assert final_state["verification"]["confidence"] >= 0.5
    assert final_state["remediation"]["status"] in {"dry_run", "suggested", "executed"}
    assert Path(final_state["code_fix"]["artifact_path"]).exists()
    assert Path(final_state["postmortem"]["path"]).exists()
