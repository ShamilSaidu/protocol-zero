"""Unit tests for the phase 2 detection engine."""

from __future__ import annotations

from monitoring.detector import IncidentDetector, service_name_from_workload
from monitoring.models import DetectionThresholds, MetricsSnapshot


class StubCollector:
    def __init__(self, snapshot: MetricsSnapshot) -> None:
        self.snapshot = snapshot

    def collect(self) -> MetricsSnapshot:
        return self.snapshot


def test_service_name_from_workload_handles_kubernetes_pod_names() -> None:
    assert service_name_from_workload("cartservice-546c548494-795fd") == "cartservice"
    assert service_name_from_workload("paymentservice") == "paymentservice"
    assert service_name_from_workload("frontend-canary-abcde") == "frontend"


def test_detector_emits_incidents_for_threshold_breaches() -> None:
    snapshot = MetricsSnapshot(
        pod_restarts={"cartservice-546c548494-795fd": 5},
        cpu_usage_pct={"checkoutservice-75b9cd684f-7b4bm": 91.5},
        memory_usage_mb={"frontend-694b9f76cd-l9cnb": 768.0},
        unavailable_replicas={"paymentservice": 1},
    )
    detector = IncidentDetector(
        collector=StubCollector(snapshot),
        thresholds=DetectionThresholds(
            pod_restart_threshold=3,
            cpu_threshold_pct=85.0,
            memory_threshold_mb=512.0,
            deployment_unavailable_threshold=1,
        ),
    )

    incidents = detector.collect_and_detect()

    assert len(incidents) == 4
    incident_types = {incident["type"] for incident in incidents}
    assert incident_types == {
        "pod_restart_loop",
        "cpu_spike",
        "memory_spike",
        "deployment_unavailable",
    }
    for incident in incidents:
        assert incident["incident_id"].startswith("INC-")
        assert incident["metrics_snapshot"]["pod_restarts"] == {"cartservice-546c548494-795fd": 5}
        assert incident["namespace"] == "default"


def test_detector_skips_metrics_below_threshold() -> None:
    snapshot = MetricsSnapshot(
        pod_restarts={"cartservice-546c548494-795fd": 1},
        cpu_usage_pct={"checkoutservice-75b9cd684f-7b4bm": 20.0},
        memory_usage_mb={"frontend-694b9f76cd-l9cnb": 128.0},
        unavailable_replicas={"paymentservice": 0},
    )
    detector = IncidentDetector(collector=StubCollector(snapshot))

    assert detector.collect_and_detect() == []
