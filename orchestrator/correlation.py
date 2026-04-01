"""Correlation and hypothesis selection for multi-agent findings."""

from __future__ import annotations

from typing import Any

from integrations.llm_client import LLMClient


class CorrelationEngine:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def correlate(self, incident: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
        hypotheses: list[dict[str, Any]] = []
        for finding in findings:
            for hypothesis in finding.get("hypotheses", []):
                hypotheses.append({
                    **hypothesis,
                    "agent_name": finding.get("agent_name", "unknown"),
                    "finding_summary": finding.get("summary", ""),
                    "evidence": finding.get("evidence", []),
                })

        if not hypotheses:
            return {
                "root_cause": f"Unresolved {incident.get('type', 'incident')}",
                "confidence": 0.45,
                "supporting_agents": [],
                "recommended_action": "Escalate to a human for manual triage.",
                "summary": "No agent produced a strong hypothesis.",
                "evidence": [],
            }

        best = max(hypotheses, key=lambda item: float(item.get("confidence", 0.0)))
        supporting_agents = [
            finding.get("agent_name", "unknown")
            for finding in findings
            if any(h.get("root_cause") == best.get("root_cause") for h in finding.get("hypotheses", []))
        ]
        evidence: list[str] = []
        for finding in findings:
            evidence.extend(finding.get("evidence", []))
        evidence = evidence[:10]

        prompt = f"""
You are a correlation engine. Return strict JSON with keys:
summary, confidence, root_cause, recommended_action, evidence.
Incident: {incident}
Findings: {findings}
Tentative best hypothesis: {best}
"""
        enriched = self.llm.generate_json(prompt)
        if isinstance(enriched, dict) and enriched.get("root_cause"):
            return {
                "root_cause": enriched.get("root_cause"),
                "confidence": float(enriched.get("confidence", best.get("confidence", 0.0))),
                "supporting_agents": supporting_agents,
                "recommended_action": enriched.get("recommended_action", best.get("recommended_action")),
                "summary": enriched.get("summary", best.get("finding_summary", "")),
                "evidence": enriched.get("evidence", evidence),
            }

        return {
            "root_cause": best.get("root_cause", "Unknown root cause"),
            "confidence": float(best.get("confidence", 0.0)),
            "supporting_agents": supporting_agents,
            "recommended_action": best.get("recommended_action"),
            "summary": best.get("finding_summary", best.get("rationale", "")),
            "evidence": evidence,
        }
