"""Threshold-based anomaly detector for phase 2 incidents."""

from __future__ import annotations

import os
import time
from typing import Iterable

from monitoring.metrics_collector import MetricsCollector
from monitoring.models import DetectionThresholds, Incident, MetricsSnapshot, build_incident_id, utc_now_iso


class IncidentDetector:
    """Converts Prometheus metrics into normalized incident payloads."""

    def __init__(
        self,
        collector: MetricsCollector | None = None,
        thresholds: DetectionThresholds | None = None,
        namespace: str | None = None,
    ) -> None:
        self.collector = collector or MetricsCollector(namespace=namespace)
        self.thresholds = thresholds or DetectionThresholds()
        self.namespace = namespace or os.getenv("KUBE_NAMESPACE", "default")

    def collect_and_detect(self) -> list[dict[str, object]]:
        snapshot = self.collector.collect()
        return [incident.as_dict() for incident in self.detect(snapshot)]

    def detect(self, snapshot: MetricsSnapshot) -> list[Incident]:
        incidents: list[Incident] = []
        incidents.extend(self._detect_restart_loops(snapshot))
        incidents.extend(self._detect_cpu_spikes(snapshot))
        incidents.extend(self._detect_memory_spikes(snapshot))
        incidents.extend(self._detect_deployment_outages(snapshot))
        return incidents

    def run_forever(self, interval_seconds: int | None = None) -> Iterable[list[dict[str, object]]]:
        interval = interval_seconds or int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
        while True:
            yield self.collect_and_detect()
            time.sleep(interval)

    def _detect_restart_loops(self, snapshot: MetricsSnapshot) -> list[Incident]:
        incidents: list[Incident] = []
        for pod, value in snapshot.pod_restarts.items():
            if value < self.thresholds.pod_restart_threshold:
                continue
            service = service_name_from_workload(pod)
            incidents.append(
                self._build_incident(
                    incident_type="pod_restart_loop",
                    severity="critical",
                    service=service,
                    pod=pod,
                    alert_name="PodRestartLoop",
                    error_message=(
                        f"Pod {pod} has restarted {int(value)} times "
                        f"(threshold: {self.thresholds.pod_restart_threshold})"
                    ),
                    snapshot=snapshot,
                )
            )
        return incidents

    def _detect_cpu_spikes(self, snapshot: MetricsSnapshot) -> list[Incident]:
        incidents: list[Incident] = []
        for pod, value in snapshot.cpu_usage_pct.items():
            if value < self.thresholds.cpu_threshold_pct:
                continue
            service = service_name_from_workload(pod)
            incidents.append(
                self._build_incident(
                    incident_type="cpu_spike",
                    severity="high",
                    service=service,
                    pod=pod,
                    alert_name="HighCPUUsage",
                    error_message=(
                        f"Pod {pod} is using {value:.2f}% CPU "
                        f"(threshold: {self.thresholds.cpu_threshold_pct:.2f}%)"
                    ),
                    snapshot=snapshot,
                )
            )
        return incidents

    def _detect_memory_spikes(self, snapshot: MetricsSnapshot) -> list[Incident]:
        incidents: list[Incident] = []
        for pod, value in snapshot.memory_usage_mb.items():
            if value < self.thresholds.memory_threshold_mb:
                continue
            service = service_name_from_workload(pod)
            incidents.append(
                self._build_incident(
                    incident_type="memory_spike",
                    severity="high",
                    service=service,
                    pod=pod,
                    alert_name="HighMemoryUsage",
                    error_message=(
                        f"Pod {pod} is using {value:.2f} MB memory "
                        f"(threshold: {self.thresholds.memory_threshold_mb:.2f} MB)"
                    ),
                    snapshot=snapshot,
                )
            )
        return incidents

    def _detect_deployment_outages(self, snapshot: MetricsSnapshot) -> list[Incident]:
        incidents: list[Incident] = []
        for deployment, value in snapshot.unavailable_replicas.items():
            if value < self.thresholds.deployment_unavailable_threshold:
                continue
            incidents.append(
                self._build_incident(
                    incident_type="deployment_unavailable",
                    severity="critical",
                    service=deployment,
                    pod=None,
                    alert_name="DeploymentUnavailable",
                    error_message=(
                        f"Deployment {deployment} has {int(value)} unavailable replicas "
                        f"(threshold: {self.thresholds.deployment_unavailable_threshold})"
                    ),
                    snapshot=snapshot,
                )
            )
        return incidents

    def _build_incident(
        self,
        incident_type: str,
        severity: str,
        service: str,
        pod: str | None,
        alert_name: str,
        error_message: str,
        snapshot: MetricsSnapshot,
    ) -> Incident:
        return Incident(
            incident_id=build_incident_id(),
            type=incident_type,
            severity=severity,
            service_affected=service,
            pod=pod,
            detected_at=utc_now_iso(),
            error_message=error_message,
            alert_name=alert_name,
            metrics_snapshot=snapshot.as_dict(),
            namespace=self.namespace,
        )


def service_name_from_workload(name: str) -> str:
    """Infer the service name from a Kubernetes pod or workload name."""
    parts = name.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:-2])
    if len(parts) == 2:
        return parts[0]
    return name
