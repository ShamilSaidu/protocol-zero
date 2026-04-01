"""Thin kubectl wrapper used by investigation and remediation flows."""

from __future__ import annotations

import json
import subprocess
from typing import Any


class KubectlClient:
    def __init__(self, namespace: str = "default") -> None:
        self.namespace = namespace

    def available(self) -> bool:
        result = self._run(["version", "--client"], expect_json=False)
        return result["returncode"] == 0

    def list_services(self) -> list[str]:
        data = self._json(["get", "svc", "-n", self.namespace, "-o", "json"])
        items = data.get("items", []) if isinstance(data, dict) else []
        return [item.get("metadata", {}).get("name", "") for item in items if item.get("metadata", {}).get("name")]

    def get_pods(self, service: str) -> list[dict[str, Any]]:
        data = self._json(["get", "pods", "-n", self.namespace, "-l", f"app={service}", "-o", "json"])
        items = data.get("items", []) if isinstance(data, dict) else []
        if items:
            return items
        data = self._json(["get", "pods", "-n", self.namespace, "-o", "json"])
        items = data.get("items", []) if isinstance(data, dict) else []
        return [item for item in items if item.get("metadata", {}).get("name", "").startswith(service)]

    def get_deployment(self, service: str) -> dict[str, Any]:
        data = self._json(["get", "deployment", service, "-n", self.namespace, "-o", "json"])
        return data if isinstance(data, dict) else {}

    def get_recent_events(self, service: str | None = None, limit: int = 12) -> list[str]:
        data = self._json(["get", "events", "-n", self.namespace, "-o", "json"])
        items = data.get("items", []) if isinstance(data, dict) else []
        messages: list[str] = []
        for item in items:
            involved = item.get("involvedObject", {})
            name = involved.get("name", "")
            if service and service not in name:
                continue
            reason = item.get("reason", "Unknown")
            message = item.get("message", "")
            messages.append(f"{reason}: {message}".strip())
        return messages[-limit:]

    def get_logs(self, pod: str, tail_lines: int = 120) -> str:
        result = self._run(["logs", pod, "-n", self.namespace, "--tail", str(tail_lines)], expect_json=False)
        return result.get("stdout", "") if result["returncode"] == 0 else result.get("stderr", "")

    def delete_pod(self, pod: str) -> dict[str, Any]:
        return self._run(["delete", "pod", pod, "-n", self.namespace], expect_json=False)

    def rollout_restart(self, deployment: str) -> dict[str, Any]:
        return self._run(["rollout", "restart", f"deployment/{deployment}", "-n", self.namespace], expect_json=False)

    def rollout_undo(self, deployment: str) -> dict[str, Any]:
        return self._run(["rollout", "undo", f"deployment/{deployment}", "-n", self.namespace], expect_json=False)

    def scale_deployment(self, deployment: str, replicas: int) -> dict[str, Any]:
        return self._run(["scale", f"deployment/{deployment}", "-n", self.namespace, f"--replicas={replicas}"], expect_json=False)

    def _json(self, args: list[str]) -> dict[str, Any] | list[Any] | None:
        result = self._run(args, expect_json=True)
        return result.get("json")

    def _run(self, args: list[str], expect_json: bool) -> dict[str, Any]:
        command = ["kubectl", *args]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        payload: dict[str, Any] = {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
        if expect_json and completed.returncode == 0:
            try:
                payload["json"] = json.loads(completed.stdout or "{}")
            except json.JSONDecodeError:
                payload["json"] = None
        return payload
