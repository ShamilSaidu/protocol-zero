"""Post-mortem generation for completed incident flows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from integrations.llm_client import LLMClient


class PostMortemGenerator:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.output_dir = Path("post_mortems")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, state: dict[str, Any]) -> dict[str, Any]:
        incident = state["incident"]
        incident_id = incident.get("incident_id", "INC-UNKNOWN")
        output_path = self.output_dir / f"{incident_id}.md"
        content = self._render_markdown(state)
        output_path.write_text(content, encoding="utf-8")
        return {"status": "generated", "path": str(output_path.resolve())}

    def _render_markdown(self, state: dict[str, Any]) -> str:
        incident = state["incident"]
        hypothesis = state.get("selected_hypothesis", {})
        remediation = state.get("remediation", {})
        findings = state.get("investigation_findings", [])
        prompt = f"""
Return strict JSON with keys summary, contributing_factors, prevention.
Incident: {incident}
Hypothesis: {hypothesis}
Findings: {findings}
Remediation: {remediation}
"""
        llm_result = self.llm.generate_json(prompt) or {}
        contributing = llm_result.get("contributing_factors", []) or ["Detailed agent findings are listed below."]
        prevention = llm_result.get("prevention", []) or ["Add targeted tests and tighter operational runbooks for this failure mode."]
        action_lines = []
        for action in remediation.get("actions", []):
            action_lines.append(f"- `{action.get('kind')}` on `{action.get('target')}` -> `{action.get('status')}`")
        if not action_lines:
            action_lines.append("- No remediation action executed.")
        finding_lines = []
        for finding in findings:
            finding_lines.append(f"- **{finding.get('agent_name')}**: {finding.get('summary')} (confidence {finding.get('confidence')})")
        if not finding_lines:
            finding_lines.append("- No agent findings were recorded.")
        contributing_lines = "\n".join([f"- {item}" for item in contributing])
        prevention_lines = "\n".join([f"- {item}" for item in prevention])
        return f"""# Post-Mortem: {incident.get('incident_id')}

## Incident Summary
- Service: `{incident.get('service_affected')}`
- Type: `{incident.get('type')}`
- Severity: `{incident.get('severity')}`
- Detected at: `{incident.get('detected_at')}`
- Selected root cause: {hypothesis.get('root_cause', 'Unknown')}
- Confidence: {hypothesis.get('confidence', 'N/A')}

## What Happened
{llm_result.get('summary', incident.get('error_message', 'No summary available.'))}

## Agent Findings
{chr(10).join(finding_lines)}

## Remediation
{chr(10).join(action_lines)}

## Contributing Factors
{contributing_lines}

## Prevention
{prevention_lines}
"""
