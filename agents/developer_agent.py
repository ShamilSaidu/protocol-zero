"""Code and change focused investigation agent."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from integrations.git_tools import GitTools
from integrations.llm_client import LLMClient
from integrations.service_catalog import get_service_info


class DeveloperAgent:
    name = "DeveloperAgent"

    def __init__(self, git_tools: GitTools | None = None, llm: LLMClient | None = None) -> None:
        self.git_tools = git_tools or GitTools()
        self.llm = llm or LLMClient()

    async def investigate(self, incident: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._investigate_sync, incident)

    def _investigate_sync(self, incident: dict[str, Any]) -> dict[str, Any]:
        service = incident.get("service_affected", "unknown")
        info = get_service_info(service)
        source_path = info.source_path
        path_exists = bool(source_path and os.path.exists(source_path))
        tracked = self.git_tools.tracked(source_path) if source_path else False
        commits = self.git_tools.recent_commits(source_path if tracked else None, max_count=5)
        fallback = self._fallback_finding(incident, info.language, info.file_hints, commits, path_exists, tracked)

        prompt = f"""
You are a software debugging agent. Return strict JSON with keys:
summary, confidence, root_cause, rationale, recommended_action, evidence.
Incident: {incident}
Service language: {info.language}
Source path exists: {path_exists}
Tracked in local git: {tracked}
File hints: {info.file_hints}
Recent commits: {commits}
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
        language: str,
        file_hints: list[str],
        commits: list[str],
        path_exists: bool,
        tracked: bool,
    ) -> dict[str, Any]:
        incident_type = incident.get("type", "unknown")
        service = incident.get("service_affected", "unknown")
        root_cause = f"Recent code or configuration regression in {service}"
        rationale = "The service source area is the most likely location for a persistent application-level regression."
        recommended_action = "Inspect the service entrypoint and recent business-logic changes before applying a code fix."
        confidence = 0.62

        if incident_type == "memory_spike":
            root_cause = f"Memory-intensive code path in {service}"
            rationale = "The issue is consistent with unbounded allocations or an expensive request path."
            recommended_action = "Review allocation-heavy handlers and add guardrails or caching where appropriate."
            confidence = 0.68
        elif incident_type == "cpu_spike":
            root_cause = f"Inefficient compute path in {service}"
            rationale = "CPU spikes often track to hot loops, synchronous bottlenecks, or expensive serialization logic."
            recommended_action = "Profile likely hotspots and inspect recent performance-sensitive changes."
            confidence = 0.66

        evidence = [
            f"Language: {language}",
            f"Source path present: {path_exists}",
            f"Tracked in local git: {tracked}",
            f"File hints: {file_hints or ['none']}",
        ]
        if commits:
            evidence.extend([f"Recent commit: {item}" for item in commits[:3]])
        else:
            evidence.append("No relevant tracked git history was found for the service path.")

        return {
            "agent_name": self.name,
            "summary": f"Code-level review points to {root_cause.lower()}.",
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
            "raw_context": {"file_hints": file_hints, "recent_commits": commits},
        }
