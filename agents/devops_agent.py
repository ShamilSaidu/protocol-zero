"""Kubernetes and deployment focused investigation agent."""

from __future__ import annotations

import asyncio
from typing import Any

from integrations.kubectl_client import KubectlClient
from integrations.llm_client import LLMClient
from integrations.service_catalog import get_service_info


class DevOpsAgent:
    name = "DevOpsAgent"

    def __init__(self, kubectl: KubectlClient, llm: LLMClient | None = None) -> None:
        self.kubectl = kubectl
        self.llm = llm or LLMClient()

    async def investigate(self, incident: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._investigate_sync, incident)

    def _investigate_sync(self, incident: dict[str, Any]) -> dict[str, Any]:
        service = incident.get("service_affected", "unknown")
        deployment = self.kubectl.get_deployment(get_service_info(service).deployment)
        pods = self.kubectl.get_pods(service)
        events = self.kubectl.get_recent_events(service)
        fallback = self._fallback_finding(incident, deployment, pods, events)

        prompt = f"""
You are an infrastructure diagnostics agent. Return strict JSON with keys:
summary, confidence, root_cause, rationale, recommended_action, evidence.
Incident: {incident}
Deployment JSON: {deployment}
Pods count: {len(pods)}
Recent events: {events}
"""
        enriched = self.llm.generate_json(prompt)
        if isinstance(enriched, dict) and enriched.get("root_cause"):
            return {
                **fallback,
                "summary": enriched.get("summary", fallback["summary"]),
                "confidence": float(enriched.get("confidence", fallback["confidence"])),
                "evidence": enriched.get("evidence", fallback["evidence"]),
                "hypotheses": [
                    {
                        "root_cause": enriched.get("root_cause"),
                        "confidence": float(enriched.get("confidence", fallback["confidence"])),
                        "rationale": enriched.get("rationale", fallback["hypotheses"][0]["rationale"]),
                        "recommended_action": enriched.get("recommended_action", fallback["hypotheses"][0]["recommended_action"]),
                    }
                ],
            }
        return fallback

    def _fallback_finding(
        self,
        incident: dict[str, Any],
        deployment: dict[str, Any],
        pods: list[dict[str, Any]],
        events: list[str],
    ) -> dict[str, Any]:
        service = incident.get("service_affected", "unknown")
        incident_type = incident.get("type", "unknown")
        status = deployment.get("status", {}) if isinstance(deployment, dict) else {}
        unavailable = int(status.get("unavailableReplicas", 0) or 0)
        available = int(status.get("availableReplicas", 0) or 0)
        root_cause = f"Kubernetes rollout or runtime health issue in {service}"
        rationale = "Cluster state indicates the workload is unhealthy or not maintaining healthy replicas."
        recommended_action = "Review deployment rollout health and restart or roll back the deployment if the issue persists."
        confidence = 0.76 if unavailable else 0.69

        if incident_type == "deployment_unavailable":
            confidence = 0.88
        elif incident_type == "pod_restart_loop":
            recommended_action = "Delete the failing pod to trigger rescheduling, then inspect logs and deployment history."
            confidence = 0.81
        elif incident_type in {"cpu_spike", "memory_spike"}:
            recommended_action = "Consider a short-term scale-out while investigating cluster or service pressure sources."
            confidence = 0.83

        evidence = [
            f"Observed pods: {len(pods)}",
            f"Available replicas: {available}",
            f"Unavailable replicas: {unavailable}",
        ]
        if events:
            evidence.extend(events[-4:])

        return {
            "agent_name": self.name,
            "summary": f"Infrastructure evidence points to {root_cause.lower()}.",
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
            "raw_context": {"deployment": deployment, "pod_count": len(pods), "events": events},
        }
