"""Scenario adapters for the benchmark harness.

This module attempts to run real chaos injections using either the bundled
`scripts/chaos.ps1` PowerShell script or the `integrations.kubectl_client.KubectlClient`.
Each adapter exposes `inject()` and `restore()`.
"""
from __future__ import annotations

import shlex
import subprocess
import shutil
from typing import Any, Dict

from integrations.kubectl_client import KubectlClient


class ScenarioAdapter:
    def __init__(self, name: str):
        self.name = name
        self.k = KubectlClient()
        # record state to allow a best-effort restore
        self._state: Dict[str, Any] = {}

    def _run_ps_action(self, action: str, service: str = "frontend") -> Dict[str, Any]:
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        script = "scripts/chaos.ps1"
        if not pwsh or not shutil.which("kubectl"):
            return {"status": "kubectl-or-pwsh-missing"}
        cmd = [pwsh, "-File", script, "-Action", action, "-Service", service]
        completed = subprocess.run(cmd, capture_output=True, text=True)
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}

    def inject(self, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run:
            return {"status": "dry-run-injected"}
        # Map scenario name to real actions
        if self.name == "kill-pod":
            # prefer kubectl client if available
            pods = self.k.get_pods("frontend")
            if pods:
                pod = pods[0].get("metadata", {}).get("name")
                self._state["deleted_pod"] = pod
                return self.k.delete_pod(pod)
            return self._run_ps_action("kill-pod", service="frontend")
        if self.name == "restart-deployment":
            return self.k.rollout_restart("frontend")
        if self.name in ("scale-to-0", "deployment-outage", "scale_down"):
            return self.k.scale_deployment("frontend", 0)
        if self.name == "scale-to-N":
            return self.k.scale_deployment("frontend", 2)
        if self.name in ("cpu-stress", "mem-stress"):
            # best-effort: restart deployment to cause disruption if no stress tooling
            return self.k.rollout_restart("frontend")
        # fallback: try the PowerShell script interface
        return self._run_ps_action(self.name, service="frontend")

    def restore(self, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run:
            return {"status": "dry-run-restored"}
        # Restore actions based on recorded state
        if "deleted_pod" in self._state:
            # pods will be recreated by deployment; nothing to do
            return {"status": "pod-will-recreate"}
        if self.name in ("scale-to-0", "deployment-outage"):
            # scale back to 1 replica
            return self.k.scale_deployment("frontend", 1)
        return {"status": "restored"}


DEFAULT_SCENARIOS = {name: ScenarioAdapter(name) for name in (
    "kill-pod",
    "crash-container",
    "scale-to-0",
    "cpu-stress",
    "mem-stress",
    "restart-deployment",
    "deployment_outage",
    "scale_down",
)}


def get_adapter(name: str) -> ScenarioAdapter:
    if name in DEFAULT_SCENARIOS:
        return DEFAULT_SCENARIOS[name]
    raise KeyError(f"Unknown scenario: {name}")
