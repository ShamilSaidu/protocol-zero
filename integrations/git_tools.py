"""Local git helpers used by the developer agent."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitTools:
    def __init__(self, repo_root: str | None = None) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[1])

    def current_branch(self) -> str:
        return self._run(["git", "branch", "--show-current"]).strip()

    def remote_url(self) -> str:
        return self._run(["git", "remote", "get-url", "origin"]).strip()

    def recent_commits(self, path_hint: str | None = None, max_count: int = 5) -> list[str]:
        command = ["git", "log", f"-n{max_count}", "--oneline"]
        if path_hint:
            command.extend(["--", path_hint])
        output = self._run(command)
        return [line.strip() for line in output.splitlines() if line.strip()]

    def tracked(self, path_hint: str | None) -> bool:
        if not path_hint:
            return False
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path_hint],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0

    def _run(self, command: list[str]) -> str:
        completed = subprocess.run(command, cwd=self.repo_root, capture_output=True, text=True)
        if completed.returncode != 0:
            return ""
        return completed.stdout
