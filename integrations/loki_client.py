"""Minimal Loki client for fetching recent demo logs."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx


class LokiClient:
    """Fetches recent log lines from a Loki HTTP API."""

    def __init__(self, base_url: str | None = None, namespace: str | None = None, client: httpx.Client | None = None) -> None:
        self.base_url = (base_url or os.getenv("LOKI_URL", "")).rstrip("/")
        self.namespace = namespace or os.getenv("KUBE_NAMESPACE", "default")
        self._client = client or httpx.Client(timeout=5.0)

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "available": self.available(),
            "base_url": self.base_url or None,
        }

    def available(self) -> bool:
        if not self.base_url:
            return False
        try:
            response = self._client.get(f"{self.base_url}/ready")
            return response.status_code == 200
        except Exception:
            return False

    def query_logs(self, service: str | None = None, limit: int = 100, since_minutes: int = 15) -> dict[str, Any]:
        query = self._build_query(service)
        if not self.base_url:
            return {"query": query, "logs": [], "available": False}

        end_ns = int(time.time() * 1_000_000_000)
        start_ns = end_ns - (since_minutes * 60 * 1_000_000_000)
        try:
            response = self._client.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": start_ns,
                    "end": end_ns,
                    "limit": limit,
                    "direction": "BACKWARD",
                },
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "query": query,
                "logs": self._parse_streams(payload),
                "available": True,
            }
        except Exception as exc:
            return {"query": query, "logs": [], "available": False, "error": str(exc)}

    def _build_query(self, service: str | None) -> str:
        labels = [f'namespace="{self.namespace}"']
        if service:
            labels.append(f'app="{service}"')
        return "{" + ",".join(labels) + "}"

    @staticmethod
    def _parse_streams(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        results = data.get("result", []) if isinstance(data, dict) else []
        logs: list[dict[str, Any]] = []
        for stream in results:
            labels = stream.get("stream", {})
            values = stream.get("values", [])
            for timestamp_ns, line in values:
                logs.append(
                    {
                        "timestamp_ns": timestamp_ns,
                        "labels": labels,
                        "line": line,
                    }
                )
        logs.sort(key=lambda item: item.get("timestamp_ns", ""), reverse=True)
        return logs
