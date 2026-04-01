"""Safe GitHub PR creation for generated fix artifacts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from github import Github
from github.GithubException import GithubException


class GitHubPRService:
    def __init__(self, repo_root: str | None = None) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[1])
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.repo_name = os.getenv("GITHUB_REPO", "")
        self.allow_write = os.getenv("ALLOW_GITHUB_WRITE", "false").lower() == "true"

    def maybe_create_pull_request(
        self,
        title: str,
        body: str,
        artifact_path: str,
        branch_name: str,
    ) -> dict[str, Any]:
        if not self.allow_write:
            return {"status": "skipped", "reason": "ALLOW_GITHUB_WRITE is false", "pull_request_url": None}
        if not self.token or not self.repo_name:
            return {"status": "skipped", "reason": "GitHub credentials are not configured", "pull_request_url": None}

        artifact = Path(artifact_path)
        if not artifact.exists():
            return {"status": "skipped", "reason": "Artifact file does not exist", "pull_request_url": None}

        client = Github(self.token)
        repo = client.get_repo(self.repo_name)
        base_branch = repo.default_branch
        base_sha = repo.get_git_ref(f"heads/{base_branch}").object.sha
        try:
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        except GithubException as exc:
            if exc.status != 422:
                return {"status": "failed", "reason": str(exc), "pull_request_url": None}

        relative_path = artifact.relative_to(self.repo_root).as_posix()
        content = artifact.read_text(encoding="utf-8")
        try:
            try:
                existing = repo.get_contents(relative_path, ref=branch_name)
            except GithubException:
                existing = None
            if existing:
                repo.update_file(relative_path, f"Update generated fix plan for {title}", content, existing.sha, branch=branch_name)
            else:
                repo.create_file(relative_path, f"Add generated fix plan for {title}", content, branch=branch_name)
            pr = repo.create_pull(title=title, body=body, head=branch_name, base=base_branch)
            return {"status": "created", "pull_request_url": pr.html_url, "branch_name": branch_name}
        except GithubException as exc:
            return {"status": "failed", "reason": str(exc), "pull_request_url": None}
