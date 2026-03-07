"""Prometheus metric collection and normalization helpers."""

from __future__ import annotations

import os
from typing import Any

from prometheus_api_client import PrometheusConnect

from monitoring.models import MetricsSnapshot


class MetricsCollector:
    """Collects the subset of Prometheus metrics needed for phase 2."""

    def __init__(self, prometheus_url: str | None = None, namespace: str | None = None) -> None:
        self.prometheus_url = prometheus_url or os.getenv("PROMETHEUS_URL", "http://localhost:9090")
        self.namespace = namespace or os.getenv("KUBE_NAMESPACE", "default")
        self.client = PrometheusConnect(url=self.prometheus_url, disable_ssl=True)

    def collect(self) -> MetricsSnapshot:
        """Fetch and normalize metrics into a detector-friendly snapshot."""
        return MetricsSnapshot(
            pod_restarts=self._fetch_pod_restarts(),
            cpu_usage_pct=self._fetch_cpu_usage_pct(),
            memory_usage_mb=self._fetch_memory_usage_mb(),
            unavailable_replicas=self._fetch_unavailable_replicas(),
        )

    def _run_query(self, query: str) -> list[dict[str, Any]]:
        result = self.client.custom_query(query=query)
        return result if isinstance(result, list) else []

    def _vector_to_map(self, vector: list[dict[str, Any]], label: str, scale: float = 1.0) -> dict[str, float]:
        values: dict[str, float] = {}
        for sample in vector:
            metric = sample.get("metric", {})
            key = metric.get(label)
            raw_value = sample.get("value", [None, None])[1]
            if not key or raw_value is None:
                continue
            try:
                values[key] = round(float(raw_value) * scale, 2)
            except (TypeError, ValueError):
                continue
        return values

    def _fetch_pod_restarts(self) -> dict[str, float]:
        query = (
            "sum by (pod) (kube_pod_container_status_restarts_total"
            f"{{namespace=\"{self.namespace}\"}})"
        )
        return self._vector_to_map(self._run_query(query), label="pod")

    def _fetch_cpu_usage_pct(self) -> dict[str, float]:
        query = (
            "sum by (pod) (rate(container_cpu_usage_seconds_total"
            f"{{namespace=\"{self.namespace}\", pod!=\"\"}}[5m])) * 100"
        )
        return self._vector_to_map(self._run_query(query), label="pod")

    def _fetch_memory_usage_mb(self) -> dict[str, float]:
        query = (
            "sum by (pod) (container_memory_working_set_bytes"
            f"{{namespace=\"{self.namespace}\", pod!=\"\"}}) / 1024 / 1024"
        )
        return self._vector_to_map(self._run_query(query), label="pod")

    def _fetch_unavailable_replicas(self) -> dict[str, float]:
        query = (
            "kube_deployment_status_replicas_unavailable"
            f"{{namespace=\"{self.namespace}\"}}"
        )
        return self._vector_to_map(self._run_query(query), label="deployment")
