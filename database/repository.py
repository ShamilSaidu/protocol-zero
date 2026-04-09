"""Persistence layer for incidents and orchestration state."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    incident_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    service_affected: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    source: Mapped[str] = mapped_column(String(64), default="prometheus")
    payload_json: Mapped[str] = mapped_column(Text)
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    postmortem_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class IncidentRepository:
    """Stores and retrieves Protocol Zero incident lifecycle state."""

    TERMINAL_STATUSES = {"resolved", "closed"}

    def __init__(self, database_url: str | None = None) -> None:
        configured = database_url or os.getenv("DATABASE_URL", "")
        fallback_path = Path("protocol_zero.db").resolve()
        fallback_url = f"sqlite:///{fallback_path.as_posix()}"
        self.database_url = configured or fallback_url
        self.effective_database_url = self.database_url
        self.engine = self._create_engine(self.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        try:
            Base.metadata.create_all(self.engine)
        except OperationalError:
            self.effective_database_url = fallback_url
            self.engine = self._create_engine(fallback_url)
            self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
            Base.metadata.create_all(self.engine)

    def _create_engine(self, database_url: str):
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        return create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)

    def upsert_incident(self, incident: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
        fingerprint = self.build_fingerprint(incident)
        state_json = json.dumps(state or {}, default=str)
        payload_json = json.dumps(incident, default=str)
        with self.SessionLocal() as session:
            record = session.scalar(select(IncidentRecord).where(IncidentRecord.incident_id == incident["incident_id"]))
            if record is None:
                record = IncidentRecord(
                    incident_id=incident["incident_id"],
                    fingerprint=fingerprint,
                    incident_type=incident.get("type", "unknown"),
                    severity=incident.get("severity", "unknown"),
                    service_affected=incident.get("service_affected", "unknown"),
                    status=incident.get("status", "active"),
                    source=incident.get("source", "prometheus"),
                    payload_json=payload_json,
                    state_json=state_json,
                )
                session.add(record)
            else:
                record.fingerprint = fingerprint
                record.incident_type = incident.get("type", record.incident_type)
                record.severity = incident.get("severity", record.severity)
                record.service_affected = incident.get("service_affected", record.service_affected)
                record.status = incident.get("status", record.status)
                record.source = incident.get("source", record.source)
                record.payload_json = payload_json
                record.state_json = state_json
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def save_state(self, incident_id: str, state: dict[str, Any]) -> dict[str, Any] | None:
        with self.SessionLocal() as session:
            record = session.scalar(select(IncidentRecord).where(IncidentRecord.incident_id == incident_id))
            if record is None:
                return None
            record.state_json = json.dumps(state, default=str)
            record.status = state.get("status", record.status)
            record.summary = state.get("summary") or record.summary
            postmortem = state.get("postmortem", {})
            if isinstance(postmortem, dict):
                record.postmortem_path = postmortem.get("path") or record.postmortem_path
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self.SessionLocal() as session:
            record = session.scalar(select(IncidentRecord).where(IncidentRecord.incident_id == incident_id))
            return self._to_dict(record) if record else None

    def list_incidents(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.SessionLocal() as session:
            stmt = select(IncidentRecord).order_by(IncidentRecord.created_at.desc()).limit(limit)
            return [self._to_dict(record) for record in session.scalars(stmt)]

    def recent_fingerprint(self, fingerprint: str, window_minutes: int = 10) -> dict[str, Any] | None:
        cutoff = utc_now().timestamp() - (window_minutes * 60)
        with self.SessionLocal() as session:
            records = session.scalars(
                select(IncidentRecord)
                .where(IncidentRecord.fingerprint == fingerprint)
                .order_by(IncidentRecord.created_at.desc())
                .limit(5)
            )
            for record in records:
                created_ts = self._timestamp(record.created_at)
                status = (record.status or "").lower()
                if created_ts >= cutoff and status not in self.TERMINAL_STATUSES:
                    return self._to_dict(record)
            return None

    def stats(self) -> dict[str, Any]:
        incidents = self.list_incidents(limit=500)
        active = sum(1 for incident in incidents if incident.get("status") not in {"resolved", "closed"})
        resolved = sum(1 for incident in incidents if incident.get("status") in {"resolved", "closed"})
        return {
            "total_incidents": len(incidents),
            "active": active,
            "resolved": resolved,
            "database_url": self.effective_database_url,
        }

    @staticmethod
    def build_fingerprint(incident: dict[str, Any]) -> str:
        return ":".join(
            [
                str(incident.get("type", "unknown")),
                str(incident.get("service_affected", "unknown")),
                str(incident.get("pod") or ""),
            ]
        )

    def _to_dict(self, record: IncidentRecord) -> dict[str, Any]:
        payload = json.loads(record.payload_json or "{}")
        state = json.loads(record.state_json or "{}")
        return {
            "incident_id": record.incident_id,
            "fingerprint": record.fingerprint,
            "incident_type": record.incident_type,
            "severity": record.severity,
            "service_affected": record.service_affected,
            "status": record.status,
            "source": record.source,
            "payload": payload,
            "state": state,
            "summary": record.summary,
            "postmortem_path": record.postmortem_path,
            "created_at": record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at),
            "updated_at": record.updated_at.isoformat() if hasattr(record.updated_at, "isoformat") else str(record.updated_at),
        }

    @staticmethod
    def _timestamp(value: Any) -> float:
        if hasattr(value, "timestamp"):
            tzinfo = getattr(value, "tzinfo", None)
            if tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.timestamp()
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.timestamp()
            except ValueError:
                return 0
        return 0
