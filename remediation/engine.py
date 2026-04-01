"""Safe remediation planning and execution."""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Any
from uuid import uuid4

from integrations.kubectl_client import KubectlClient
from integrations.service_catalog import get_service_info


class RemediationEngine:
    def __init__(self, kubectl: KubectlClient, dry_run: bool | None = None) -> None:
        self.kubectl = kubectl
        self.dry_run = dry_run if dry_run is not None else os.getenv("DRY_RUN_MODE", "true").lower() == "true"
        self.auto_threshold = float(os.getenv("CONFIDENCE_THRESHOLD_AUTO", "0.8"))
        self.max_actions_per_hour = int(os.getenv("MAX_ACTIONS_PER_HOUR", "10"))
        self.action_timestamps: deque[float] = deque()

    def plan_and_execute(self, state: dict[str, Any]) -> dict[str, Any]:
        incident = state["incident"]
        verification = state.get("verification", {})
        action = self._build_action(
            incident,
            state.get("selected_hypothesis", {}),
            verification,
            state.get("investigation_findings", []),
        )
        if not action:
            return {"status": "skipped", "actions": [], "summary": "No remediation action was applicable."}

        self._prune_old_actions()
        if len(self.action_timestamps) >= self.max_actions_per_hour:
            action["status"] = "rate_limited"
            return {"status": "rate_limited", "actions": [action], "summary": "Action budget for the hour is exhausted."}

        if not verification.get("can_auto_remediate"):
            action["status"] = "suggested"
            return {"status": "suggested", "actions": [action], "summary": action["description"]}

        if self.dry_run:
            action["status"] = "dry_run"
            return {"status": "dry_run", "actions": [action], "summary": action["description"]}

        result = self._execute_action(action)
        action["execution_result"] = result
        action["status"] = "executed" if result.get("returncode") == 0 else "failed"
        if result.get("returncode") == 0:
            self.action_timestamps.append(time.time())
        return {"status": action["status"], "actions": [action], "summary": action["description"]}

    def _build_action(
        self,
        incident: dict[str, Any],
        hypothesis: dict[str, Any],
        verification: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        service = incident.get("service_affected", "unknown")
        deployment = get_service_info(service).deployment
        incident_type = incident.get("type", "unknown")
        pod = incident.get("pod") or self._pod_from_findings(findings)
        action = {
            "action_id": f"ACT-{uuid4().hex[:8].upper()}",
            "incident_type": incident_type,
            "service": service,
            "dry_run": self.dry_run,
            "confidence": verification.get("confidence", 0.0),
            "reason": hypothesis.get("root_cause", "Unknown cause"),
        }
        if incident_type == "pod_restart_loop" and pod:
            return {
                **action,
                "kind": "delete_pod",
                "target": pod,
                "command": f"kubectl delete pod {pod} -n {incident.get('namespace', 'default')}",
                "description": "Restart the failing pod so Kubernetes schedules a fresh instance.",
            }
        if incident_type == "pod_restart_loop":
            return {
                **action,
                "kind": "rollout_restart",
                "target": deployment,
                "command": f"kubectl rollout restart deployment/{deployment} -n {incident.get('namespace', 'default')}",
                "description": "Restart the deployment when a specific failing pod target is unavailable.",
            }
        if incident_type == "deployment_unavailable":
            return {
                **action,
                "kind": "rollout_restart",
                "target": deployment,
                "command": f"kubectl rollout restart deployment/{deployment} -n {incident.get('namespace', 'default')}",
                "description": "Restart the unhealthy deployment to recover unavailable replicas.",
            }
        if incident_type in {"cpu_spike", "memory_spike"}:
            return {
                **action,
                "kind": "scale_deployment",
                "target": deployment,
                "replicas": 2,
                "command": f"kubectl scale deployment/{deployment} -n {incident.get('namespace', 'default')} --replicas=2",
                "description": "Scale the deployment to create headroom while the root cause is addressed.",
            }
        return None

    def _pod_from_findings(self, findings: list[dict[str, Any]]) -> str | None:
        for finding in findings:
            raw_context = finding.get("raw_context", {})
            pod = raw_context.get("pod")
            if pod:
                return pod
        return None

    def _execute_action(self, action: dict[str, Any]) -> dict[str, Any]:
        if action["kind"] == "delete_pod":
            return self.kubectl.delete_pod(action["target"])
        if action["kind"] == "rollout_restart":
            return self.kubectl.rollout_restart(action["target"])
        if action["kind"] == "scale_deployment":
            return self.kubectl.scale_deployment(action["target"], int(action.get("replicas", 2)))
        return {"returncode": 1, "stderr": f"Unsupported action kind: {action['kind']}"}

    def _prune_old_actions(self) -> None:
        cutoff = time.time() - 3600
        while self.action_timestamps and self.action_timestamps[0] < cutoff:
            self.action_timestamps.popleft()
