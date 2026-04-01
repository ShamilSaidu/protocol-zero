"""FastAPI application for the Protocol Zero MVP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from orchestrator.runtime import ProtocolZeroRuntime

load_dotenv()
RUNTIME = ProtocolZeroRuntime()
TEMPLATE_PATH = Path("frontend") / "templates" / "dashboard.html"


class TriggerIncidentRequest(BaseModel):
    service: str
    incident_type: str
    severity: str = "high"
    error_message: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await RUNTIME.start()
    yield
    await RUNTIME.stop()


app = FastAPI(title="Protocol Zero", version="0.1.0", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    if not TEMPLATE_PATH.exists():
        return "<h1>Protocol Zero</h1><p>Dashboard template missing.</p>"
    return TEMPLATE_PATH.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return RUNTIME.health()


@app.get("/api/stats")
def stats() -> dict:
    return RUNTIME.stats()


@app.get("/api/incidents")
def list_incidents(limit: int = 50) -> dict:
    return {"incidents": RUNTIME.list_incidents(limit=limit)}


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    incident = RUNTIME.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.post("/api/incidents/trigger")
async def trigger_incident(request: TriggerIncidentRequest) -> dict:
    return await RUNTIME.trigger_incident(
        service=request.service,
        incident_type=request.incident_type,
        severity=request.severity,
        error_message=request.error_message,
    )


@app.post("/api/incidents/detect")
async def detect_and_process(auto_process: bool = True) -> dict:
    return await RUNTIME.run_detection_cycle(auto_process=auto_process)


@app.post("/api/incidents/{incident_id}/reprocess")
async def reprocess_incident(incident_id: str) -> dict:
    incident = await RUNTIME.reprocess_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/api/postmortems/{incident_id}")
def get_postmortem(incident_id: str) -> dict:
    payload = RUNTIME.get_postmortem(incident_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return payload


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
