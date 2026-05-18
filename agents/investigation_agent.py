"""Logs and telemetry focused investigation agent."""

from __future__ import annotations

import asyncio
from typing import Any

from integrations.kubectl_client import KubectlClient
from integrations.llm_client import LLMClient


class InvestigationAgent:
    name = "InvestigationAgent"

    def __init__(self, kubectl: KubectlClient, llm: LLMClient | None = None) -> None:
        self.kubectl = kubectl
        self.llm = llm or LLMClient()

    async def investigate(self, incident: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._investigate_sync, incident)

    def _investigate_sync(self, incident: dict[str, Any]) -> dict[str, Any]:
        service = incident.get("service_affected", "unknown")
        pod = incident.get("pod") or self._pick_pod(service)
        logs = self.kubectl.get_logs(pod) if pod else "No pod logs available."
        events = self.kubectl.get_recent_events(service)
        metrics = incident.get("metrics_snapshot", {})
        fallback = self._fallback_finding(incident, pod, logs, events, metrics)

        prompt = f"""
You are an SRE investigation agent. Return strict JSON with keys:
summary, confidence, root_cause, rationale, recommended_action, evidence.
Incident: {incident}
Recent events: {events}
Logs excerpt: {logs[:2000]}
Metrics snapshot: {metrics}
"""
        enriched = self.llm.generate_json(prompt)
        if isinstance(enriched, dict) and enriched.get("root_cause"):
            hypothesis = {
                "root_cause": enriched.get("root_cause"),
                "confidence": float(enriched.get("confidence", fallback["confidence"])),
                "rationale": enriched.get("rationale", fallback["hypotheses"][0]["rationale"]),
                "recommended_action": enriched.get("recommended_action", fallback["hypotheses"][0]["recommended_action"]),
            }
            return {
                **fallback,
                "summary": enriched.get("summary", fallback["summary"]),
                "confidence": float(enriched.get("confidence", fallback["confidence"])),
                "evidence": enriched.get("evidence", fallback["evidence"]),
                "hypotheses": [hypothesis],
            }
        return fallback

    def _pick_pod(self, service: str) -> str | None:
        pods = self.kubectl.get_pods(service)
        if not pods:
            return None
        return pods[0].get("metadata", {}).get("name")

    def _fallback_finding(
        self,
        incident: dict[str, Any],
        pod: str | None,
        logs: str,
        events: list[str],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        incident_type = incident.get("type", "unknown")
        lower_logs = logs.lower()
        root_cause = "Application crash or dependency failure"
        rationale = "Incident type and runtime logs suggest the service failed while handling startup or traffic."
        recommended_action = "Inspect recent application logs and restart the impacted workload if the issue is transient."
        confidence = 0.72

        if "oomkilled" in lower_logs or "out of memory" in lower_logs:
            root_cause = "Container memory exhaustion"
            rationale = "Runtime logs indicate the process was OOM-killed or memory constrained."
            recommended_action = "Scale memory capacity or roll out a memory leak fix before restarting the workload."
            confidence = 0.86
        elif "connection refused" in lower_logs or "deadline exceeded" in lower_logs:
            root_cause = "Downstream dependency connectivity failure"
            rationale = "The service is failing because a dependency refused or timed out on requests."
            recommended_action = "Check dependent services and recover the failing upstream before repeated restarts."
            confidence = 0.81
        elif incident_type == "cpu_spike":
            root_cause = "Traffic surge or inefficient request path"
            rationale = "CPU saturation is directly measured via Prometheus metrics with high fidelity."
            recommended_action = "Scale the deployment and inspect hot code paths or recent request pattern changes."
            confidence = 0.85
        elif incident_type == "memory_spike":
            root_cause = "Memory leak or oversized working set"
            rationale = "Memory spike is directly measured via Prometheus metrics, indicating working set exceeded threshold."
            recommended_action = "Restart the workload in the short term and inspect allocation-heavy code paths."
            confidence = 0.87
        elif incident_type == "deployment_unavailable":
            root_cause = "Deployment rollout health issue"
            rationale = "Unavailable replicas indicate the deployment cannot maintain healthy pods."
            recommended_action = "Inspect deployment events and restart or roll back the deployment."
            confidence = 0.83

        evidence = [
            f"Impacted pod: {pod or 'unknown'}",
            f"Recent events observed: {len(events)}",
            f"Metrics keys: {list(metrics.keys())}",
        ]
        if logs:
            evidence.append(logs[:240].replace("\n", " "))
        if events:
            evidence.extend(events[-3:])

        return {
            "agent_name": self.name,
            "summary": f"Telemetry and logs point to {root_cause.lower()}.",
            "confidence": confidence,
            "evidence": evidence,
            "hypotheses": [
                {
                    "root_cause": root_cause,
                    "confidence": confidence,
                    "rationale": rationale,
                    "recommended_action": recommended_action,
                }
            ],
            "raw_context": {"pod": pod, "events": events, "log_excerpt": logs[:2000]},
        }
