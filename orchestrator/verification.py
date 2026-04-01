"""Verification and escalation decisions for selected hypotheses."""

from __future__ import annotations

import os
from typing import Any


class VerificationEngine:
    def __init__(self) -> None:
        self.auto_threshold = float(os.getenv("CONFIDENCE_THRESHOLD_AUTO", "0.8"))
        self.suggest_threshold = float(os.getenv("CONFIDENCE_THRESHOLD_SUGGEST", "0.5"))

    def verify(
        self,
        incident: dict[str, Any],
        selected_hypothesis: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        confidence = float(selected_hypothesis.get("confidence", 0.0))
        evidence_count = len(selected_hypothesis.get("evidence", []))
        if evidence_count < 2:
            confidence = max(0.0, confidence - 0.1)
        if incident.get("type") == "deployment_unavailable":
            confidence = min(0.95, confidence + 0.05)

        can_auto = confidence >= self.auto_threshold
        should_suggest = confidence >= self.suggest_threshold
        escalate = not should_suggest
        status = "auto_approved" if can_auto else "human_review_required"
        if escalate:
            status = "escalated"

        return {
            "confidence": round(confidence, 2),
            "can_auto_remediate": can_auto,
            "should_suggest_action": should_suggest,
            "escalate_to_human": escalate,
            "status": status,
            "reasoning_summary": (
                f"Selected root cause '{selected_hypothesis.get('root_cause', 'unknown')}' with confidence {confidence:.2f}."
            ),
            "supporting_agents": selected_hypothesis.get("supporting_agents", []),
            "evidence_count": evidence_count,
        }
