"""Runtime service that wires detection, orchestration, and persistence together."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from database.repository import IncidentRepository
from integrations.loki_client import LokiClient
from integrations.redis_store import RedisEventStore
from monitoring.detector import IncidentDetector
from monitoring.models import build_incident_id, utc_now_iso
from orchestrator.graph import ProtocolZeroOrchestrator


class ProtocolZeroRuntime:
    def __init__(self) -> None:
        self.namespace = os.getenv("KUBE_NAMESPACE", "default")
        self.detector = IncidentDetector(namespace=self.namespace)
        self.repository = IncidentRepository()
        self.orchestrator = ProtocolZeroOrchestrator(namespace=self.namespace)
        self.event_store = RedisEventStore()
        self.loki = LokiClient(namespace=self.namespace)
        self.background_enabled = os.getenv("ENABLE_BACKGROUND_DETECTOR", "false").lower() == "true"
        self._background_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.event_store.record_event(
            "runtime_started",
            "Protocol Zero runtime started.",
            {"background_detector": self.background_enabled},
        )
        if self.background_enabled and self._background_task is None:
            self._background_task = asyncio.create_task(self._background_loop())

    async def stop(self) -> None:
        self.event_store.record_event("runtime_stopped", "Protocol Zero runtime stopped.")
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

    async def _background_loop(self) -> None:
        interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
        while True:
            try:
                await self.run_detection_cycle(auto_process=True)
            except Exception as exc:
                self.event_store.record_event(
                    "background_error",
                    "Background detection cycle failed.",
                    {"error": str(exc)},
                )
            await asyncio.sleep(interval)

    async def run_detection_cycle(self, auto_process: bool = True) -> dict[str, Any]:
        incidents = await asyncio.to_thread(self.detector.collect_and_detect)
        processed: list[dict[str, Any]] = []
        skipped = 0
        for incident in incidents:
            fingerprint = self.repository.build_fingerprint(incident)
            if self.repository.recent_fingerprint(fingerprint):
                skipped += 1
                continue
            if auto_process:
                processed.append(await self.process_incident(incident))
            else:
                self.repository.upsert_incident(incident, {"status": "detected", "incident": incident})
                processed.append(incident)
        result = {
            "detected": len(incidents),
            "processed": len(processed),
            "skipped": skipped,
            "incidents": processed,
        }
        self.event_store.record_event(
            "detection_cycle",
            "Completed detection cycle.",
            {
                "auto_process": auto_process,
                "detected": result["detected"],
                "processed": result["processed"],
                "skipped": result["skipped"],
            },
        )
        return result

    async def trigger_incident(
        self,
        service: str,
        incident_type: str,
        severity: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        incident = {
            "incident_id": build_incident_id(),
            "type": incident_type,
            "severity": severity,
            "service_affected": service,
            "pod": None,
            "detected_at": utc_now_iso(),
            "error_message": error_message or f"Manual trigger: {incident_type} on {service}",
            "alert_name": f"Manual{incident_type.title().replace('_', '')}",
            "metrics_snapshot": {},
            "source": "manual",
            "namespace": self.namespace,
            "status": "active",
        }
        self.event_store.record_event(
            "manual_incident",
            f"Manual incident triggered for {service}.",
            {"incident_id": incident["incident_id"], "incident_type": incident_type, "severity": severity},
        )
        return await self.process_incident(incident)

    async def process_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        initial_state = {"status": "investigating", "incident": incident}
        self.event_store.record_event(
            "incident_processing_started",
            f"Processing incident {incident.get('incident_id')}.",
            {"incident_id": incident.get("incident_id"), "service": incident.get("service_affected")},
        )
        self.repository.upsert_incident(incident, initial_state)
        final_state = await self.orchestrator.handle_incident(incident)
        self.repository.save_state(incident["incident_id"], final_state)
        persisted = self.repository.get_incident(incident["incident_id"]) or {"payload": incident, "state": final_state}
        self.event_store.record_event(
            "incident_processing_finished",
            f"Incident {incident.get('incident_id')} reached {final_state.get('status', 'unknown')}.",
            {
                "incident_id": incident.get("incident_id"),
                "status": final_state.get("status"),
                "summary": final_state.get("summary"),
            },
        )
        return persisted

    async def reprocess_incident(self, incident_id: str) -> dict[str, Any] | None:
        existing = self.repository.get_incident(incident_id)
        if not existing:
            return None
        payload = existing.get("payload", {})
        return await self.process_incident(payload)

    def list_incidents(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.repository.list_incidents(limit=limit)

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        return self.repository.get_incident(incident_id)

    def get_postmortem(self, incident_id: str) -> dict[str, Any] | None:
        incident = self.repository.get_incident(incident_id)
        if not incident:
            return None
        path = incident.get("state", {}).get("postmortem", {}).get("path") or incident.get("postmortem_path")
        if not path or not os.path.exists(path):
            return {"path": path, "content": None}
        with open(path, encoding="utf-8") as handle:
            return {"path": path, "content": handle.read()}

    def stats(self) -> dict[str, Any]:
        stats = self.repository.stats()
        stats.update(
            {
                "dry_run_mode": os.getenv("DRY_RUN_MODE", "true").lower() == "true",
                "background_detector": self.background_enabled,
                "prometheus": self.detector.collector.status(),
                "redis": self.event_store.status(),
                "loki": self.loki.status(),
            }
        )
        return stats

    def list_events(self, limit: int = 25) -> list[dict[str, Any]]:
        return self.event_store.list_events(limit=limit)

    def query_logs(self, service: str | None = None, limit: int = 100, since_minutes: int = 15) -> dict[str, Any]:
        return self.loki.query_logs(service=service, limit=limit, since_minutes=since_minutes)

    def health(self) -> dict[str, Any]:
        prometheus_status = self.detector.collector.status()
        redis_status = self.event_store.status()
        loki_status = self.loki.status()
        dependencies = {
            "database_url": self.repository.effective_database_url,
            "prometheus": prometheus_status,
            "redis": redis_status,
            "loki": loki_status,
        }
        status = "healthy"
        if prometheus_status["configured"] and not prometheus_status["available"]:
            status = "degraded"
        if redis_status["configured"] and not redis_status["available"]:
            status = "degraded"
        if loki_status["configured"] and not loki_status["available"]:
            status = "degraded"
        return {
            "status": status,
            "namespace": self.namespace,
            "database_url": self.repository.effective_database_url,
            "dry_run_mode": os.getenv("DRY_RUN_MODE", "true").lower() == "true",
            "dependencies": dependencies,
        }
