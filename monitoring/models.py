"""Core data models for the phase 2 detection engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    """Return a stable UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class DetectionThresholds:
    """Thresholds that control when metrics become incidents."""

    pod_restart_threshold: int = 3
    cpu_threshold_pct: float = 85.0
    memory_threshold_mb: float = 500.0
    deployment_unavailable_threshold: int = 1


@dataclass(slots=True)
class MetricsSnapshot:
    """Normalized metrics used by the detector."""

    pod_restarts: dict[str, float] = field(default_factory=dict)
    cpu_usage_pct: dict[str, float] = field(default_factory=dict)
    memory_usage_mb: dict[str, float] = field(default_factory=dict)
    unavailable_replicas: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, dict[str, float]]:
        return {
            "pod_restarts": dict(self.pod_restarts),
            "cpu_usage_pct": dict(self.cpu_usage_pct),
            "memory_usage_mb": dict(self.memory_usage_mb),
            "unavailable_replicas": dict(self.unavailable_replicas),
        }


@dataclass(slots=True)
class Incident:
    """Structured incident emitted by the detection engine."""

    incident_id: str
    type: str
    severity: str
    service_affected: str
    pod: str | None
    detected_at: str
    error_message: str
    alert_name: str
    metrics_snapshot: dict[str, dict[str, float]]
    source: str = "prometheus"
    namespace: str | None = None
    status: str = "active"
    confidence: float = 0.8

    def as_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "type": self.type,
            "severity": self.severity,
            "service_affected": self.service_affected,
            "pod": self.pod,
            "detected_at": self.detected_at,
            "error_message": self.error_message,
            "alert_name": self.alert_name,
            "metrics_snapshot": self.metrics_snapshot,
            "source": self.source,
            "namespace": self.namespace,
            "status": self.status,
            "confidence": self.confidence,
        }


def build_incident_id() -> str:
    """Generate a readable incident identifier."""
    return f"INC-{uuid4().hex[:10].upper()}"
