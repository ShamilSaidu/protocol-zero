"""LangGraph-powered orchestration for Protocol Zero."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.developer_agent import DeveloperAgent
from agents.devops_agent import DevOpsAgent
from agents.investigation_agent import InvestigationAgent
from integrations.git_tools import GitTools
from integrations.github_pr import GitHubPRService
from integrations.kubectl_client import KubectlClient
from integrations.llm_client import LLMClient
from orchestrator.codefix import CodeFixGenerator
from orchestrator.correlation import CorrelationEngine
from orchestrator.verification import VerificationEngine
from post_mortem.generator import PostMortemGenerator
from remediation.engine import RemediationEngine


class ProtocolState(TypedDict, total=False):
    incident: dict[str, Any]
    current_step: str
    status: str
    started_at: str
    completed_at: str
    investigation_findings: list[dict[str, Any]]
    selected_hypothesis: dict[str, Any]
    verification: dict[str, Any]
    remediation: dict[str, Any]
    code_fix: dict[str, Any]
    postmortem: dict[str, Any]
    escalate_to_human: bool
    summary: str
    audit_log: list[str]


class ProtocolZeroOrchestrator:
    def __init__(self, namespace: str | None = None) -> None:
        self.namespace = namespace or os.getenv("KUBE_NAMESPACE", "default")
        self.llm = LLMClient()
        self.kubectl = KubectlClient(namespace=self.namespace)
        self.investigation_agent = InvestigationAgent(self.kubectl, self.llm)
        self.developer_agent = DeveloperAgent(GitTools(), self.llm)
        self.devops_agent = DevOpsAgent(self.kubectl, self.llm)
        self.correlation = CorrelationEngine(self.llm)
        self.verification = VerificationEngine()
        self.remediation = RemediationEngine(self.kubectl)
        self.code_fix = CodeFixGenerator(self.llm, GitHubPRService())
        self.post_mortem = PostMortemGenerator(self.llm)
        self.graph = self._build_graph().compile()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(ProtocolState)
        graph.add_node("investigate", self._investigate)
        graph.add_node("correlate", self._correlate)
        graph.add_node("verify", self._verify)
        graph.add_node("remediate", self._remediate)
        graph.add_node("build_code_fix", self._code_fix)
        graph.add_node("write_post_mortem", self._post_mortem)
        graph.set_entry_point("investigate")
        graph.add_edge("investigate", "correlate")
        graph.add_edge("correlate", "verify")
        graph.add_edge("verify", "remediate")
        graph.add_edge("remediate", "build_code_fix")
        graph.add_edge("build_code_fix", "write_post_mortem")
        graph.add_edge("write_post_mortem", END)
        return graph

    async def handle_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        initial_state: ProtocolState = {
            "incident": incident,
            "current_step": "received",
            "status": "investigating",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "audit_log": [f"Incident {incident.get('incident_id')} received."],
        }
        final_state = await self.graph.ainvoke(initial_state)
        final_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        return final_state

    async def _investigate(self, state: ProtocolState) -> ProtocolState:
        incident = state["incident"]
        findings = await asyncio.gather(
            self.investigation_agent.investigate(incident),
            self.developer_agent.investigate(incident),
            self.devops_agent.investigate(incident),
        )
        return {
            "current_step": "investigated",
            "investigation_findings": findings,
            "audit_log": [*state.get("audit_log", []), "Completed multi-agent investigation."],
        }

    async def _correlate(self, state: ProtocolState) -> ProtocolState:
        selected = self.correlation.correlate(state["incident"], state.get("investigation_findings", []))
        return {
            "current_step": "correlated",
            "selected_hypothesis": selected,
            "summary": selected.get("summary", ""),
            "audit_log": [*state.get("audit_log", []), "Correlated agent findings into a selected hypothesis."],
        }

    async def _verify(self, state: ProtocolState) -> ProtocolState:
        verification = self.verification.verify(
            state["incident"],
            state.get("selected_hypothesis", {}),
            state.get("investigation_findings", []),
        )
        return {
            "current_step": "verified",
            "verification": verification,
            "escalate_to_human": verification.get("escalate_to_human", False),
            "audit_log": [*state.get("audit_log", []), verification.get("reasoning_summary", "Verification completed.")],
        }

    async def _remediate(self, state: ProtocolState) -> ProtocolState:
        remediation = self.remediation.plan_and_execute(state)
        status = "needs_review"
        if remediation.get("status") in {"executed", "resolved"}:
            status = "resolved"
        elif remediation.get("status") == "dry_run":
            status = "simulated"
        elif remediation.get("status") == "suggested":
            status = "needs_review"
        return {
            "current_step": "remediated",
            "status": status,
            "remediation": remediation,
            "audit_log": [*state.get("audit_log", []), f"Remediation status: {remediation.get('status', 'unknown')}"],
        }

    async def _code_fix(self, state: ProtocolState) -> ProtocolState:
        code_fix = self.code_fix.generate(state)
        return {
            "current_step": "code_fix_generated",
            "code_fix": code_fix,
            "audit_log": [*state.get("audit_log", []), "Generated code-fix artifact and evaluated PR creation."],
        }

    async def _post_mortem(self, state: ProtocolState) -> ProtocolState:
        postmortem = self.post_mortem.generate(state)
        return {
            "current_step": "post_mortem_generated",
            "postmortem": postmortem,
            "audit_log": [*state.get("audit_log", []), "Generated post-mortem artifact."],
        }

