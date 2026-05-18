"""AI-assisted code-fix artifact generation and optional PR creation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from integrations.github_pr import GitHubPRService
from integrations.llm_client import LLMClient
from integrations.service_catalog import get_service_info


class CodeFixGenerator:
    def __init__(self, llm: LLMClient | None = None, github_service: GitHubPRService | None = None) -> None:
        self.llm = llm or LLMClient()
        self.github_service = github_service or GitHubPRService()
        self.output_dir = Path("docs") / "codefixes"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, state: dict[str, Any]) -> dict[str, Any]:
        incident = state["incident"]
        service = incident.get("service_affected", "unknown")
        info = get_service_info(service)
        incident_id = incident.get("incident_id", "INC-UNKNOWN")
        artifact_path = self.output_dir / f"{incident_id}.md"
        content = self._render_fix_plan(state, info)
        artifact_path.write_text(content, encoding="utf-8")

        branch_name = f"codex/fix-{incident_id.lower()}"
        pr = self.github_service.maybe_create_pull_request(
            title=f"Protocol Zero fix plan for {incident_id}",
            body="AI-generated fix plan based on incident investigation. Review before applying.",
            artifact_path=str(artifact_path.resolve()),
            branch_name=branch_name,
        )
        return {
            "status": "generated" if pr.get("status") in {"skipped", "created"} else "failed",
            "artifact_path": str(artifact_path.resolve()),
            "pull_request": pr,
            "branch_name": pr.get("branch_name", branch_name),
            "service": service,
        }

    def _render_fix_plan(self, state: dict[str, Any], info) -> str:
        incident = state["incident"]
        hypothesis = state.get("selected_hypothesis", {})
        findings = state.get("investigation_findings", [])
        remediation = state.get("remediation", {})
        prompt = f"""
Create a concise markdown fix plan with sections:
Summary, Likely Files, Proposed Changes, Validation Plan.
Incident: {incident}
Hypothesis: {hypothesis}
Findings: {findings}
File hints: {info.file_hints}
"""
        llm_result = self.llm.generate_json(prompt)
        proposed_changes = []
        if isinstance(llm_result, dict):
            proposed_changes = llm_result.get("proposed_changes", []) or []
        if not proposed_changes:
            proposed_changes = [
                "Review the service entrypoint and dependency wiring.",
                "Add defensive handling for the failure mode identified in the investigation.",
                "Add or extend regression tests around the impacted path.",
            ]
        file_lines = "\n".join([f"- `{item}`" for item in (info.file_hints or ["No concrete file hints available."])])
        change_lines = "\n".join([f"- {item}" for item in proposed_changes])
        validation_lines = "\n".join([
            "- Reproduce the incident locally or in Minikube.",
            "- Run service-specific tests plus the Protocol Zero e2e flow.",
            "- Confirm incident no longer reproduces after rollout.",
        ])
        
        # Build remediation actions section
        remediation_section = ""
        if remediation.get("actions"):
            action_lines = []
            for action in remediation["actions"]:
                command = action.get("command", "N/A")
                status = action.get("status", "unknown").upper()
                description = action.get("description", "")
                action_lines.append(f"- **Status**: `{status}`")
                action_lines.append(f"- **Type**: `{action.get('kind', 'unknown')}`")
                action_lines.append(f"- **Target**: `{action.get('target', 'N/A')}`")
                action_lines.append(f"- **Command**: `{command}`")
                action_lines.append(f"- **Description**: {description}")
                action_lines.append("")
            remediation_section = f"""## Remediation Actions Executed

{chr(10).join(action_lines).rstrip()}
"""
        
        return f"""# Code Fix Plan for {incident.get('incident_id')}

## Summary
- Service: `{incident.get('service_affected')}`
- Incident type: `{incident.get('type')}`
- Selected root cause: {hypothesis.get('root_cause', 'Unknown')}
- Confidence: {hypothesis.get('confidence', 'N/A')}

## Likely Files
{file_lines}

## Proposed Changes
{change_lines}

{remediation_section}## Validation Plan
{validation_lines}
"""
