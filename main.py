"""FastAPI application for the Protocol Zero MVP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import Any

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


@app.get("/api/events")
def list_events(limit: int = 25) -> dict:
    return {"events": RUNTIME.list_events(limit=limit)}


@app.get("/api/logs")
def get_logs(service: str | None = None, limit: int = 50, since_minutes: int = 15) -> dict:
    return RUNTIME.query_logs(service=service, limit=limit, since_minutes=since_minutes)


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


@app.get("/postmortems/{incident_id}", response_class=HTMLResponse)
def postmortem_page(incident_id: str) -> str:
    incident = RUNTIME.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    postmortem = RUNTIME.get_postmortem(incident_id)
    content = (postmortem or {}).get("content")
    return render_postmortem_page(incident, postmortem or {}, content)


@app.get("/codefixes/{incident_id}", response_class=HTMLResponse)
def codefix_page(incident_id: str) -> str:
    incident = RUNTIME.get_incident(incident_id)
    # Don't require incident to exist - code fix files may exist without DB entry
    if not incident:
        incident = {"incident_id": incident_id, "state": {}}
    
    codefix = RUNTIME.get_codefix(incident_id) or {}
    path = codefix.get("path")
    content = codefix.get("content")
    
    if not content:
        raise HTTPException(status_code=404, detail=f"No code fix found for {incident_id}")
    
    return render_artifact_page(
        incident=incident,
        title="Code Fix Plan",
        eyebrow="Protocol Zero Code Fix",
        artifact_label="Generated Fix Plan",
        artifact_path=path or "Not generated",
        content=content,
        empty_message="No code-fix artifact is available yet.",
    )


def render_postmortem_page(incident: dict[str, Any], postmortem: dict[str, Any], content: str | None) -> str:
    return render_artifact_page(
        incident=incident,
        title="Post-Mortem",
        eyebrow="Protocol Zero Post-Mortem",
        artifact_label="Generated Report",
        artifact_path=postmortem.get("path") or incident.get("postmortem_path") or "Not generated",
        content=content,
        empty_message="No post-mortem content is available yet.",
    )


def render_artifact_page(
    incident: dict[str, Any],
    title: str,
    eyebrow: str,
    artifact_label: str,
    artifact_path: str,
    content: str | None,
    empty_message: str,
) -> str:
    payload = incident.get("payload", {})
    state = incident.get("state", {})
    service = payload.get("service_affected") or incident.get("service_affected", "unknown")
    incident_type = payload.get("type") or incident.get("incident_type", "unknown")
    severity = payload.get("severity") or incident.get("severity", "unknown")
    status = state.get("status") or incident.get("status", "unknown")
    summary = state.get("summary") or incident.get("summary") or payload.get("error_message") or "No summary available."
    remediation = state.get("remediation", {})
    verification = state.get("verification", {})
    hypothesis = state.get("selected_hypothesis", {})
    incident_id = str(incident.get("incident_id", ""))
    rendered_content = render_artifact_markdown(content) if content else f"<div class=\"empty\">{escape(empty_message)}</div>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{escape(title)} {escape(incident_id)}</title>
  <style>
    :root{{--bg:#06101e;--panel:rgba(8,17,31,.9);--line:rgba(175,210,255,.16);--line2:rgba(175,210,255,.3);--text:#eef5ff;--muted:#92a8c7;--blue:#4db8ff;--orange:#ff9552;--green:#7fe2a2;--yellow:#ffc76a;--red:#ff7f7f;--shadow:0 24px 80px rgba(0,0,0,.34)}}
    *{{box-sizing:border-box}}body{{margin:0;min-height:100vh;color:var(--text);font-family:"Aptos","Segoe UI Variable Text",sans-serif;background:radial-gradient(circle at top left,rgba(77,184,255,.2),transparent 24%),radial-gradient(circle at top right,rgba(255,149,82,.16),transparent 20%),linear-gradient(145deg,#04101d,#091729 45%,#06111f)}}
    body:before{{content:"";position:fixed;inset:0;pointer-events:none;background:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:30px 30px;mask-image:radial-gradient(circle at center,black 32%,transparent 92%)}}
    .shell{{max-width:1320px;margin:0 auto;padding:28px 22px 56px;position:relative;z-index:1}}.panel{{background:linear-gradient(180deg,rgba(13,24,46,.92),rgba(6,12,24,.94));border:1px solid var(--line);border-radius:28px;box-shadow:var(--shadow);overflow:hidden}}.hero{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:22px;margin-bottom:22px}}.hero-main,.side,.content{{padding:26px}}.eyebrow,.label{{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}}h1,h2,h3{{font-family:"Bahnschrift","Aptos Display",sans-serif;margin:0}}h1{{font-size:clamp(34px,5vw,58px);line-height:.95;margin:10px 0 12px}}h2{{font-size:28px;margin-bottom:14px}}h3{{font-size:20px;margin-bottom:10px}}p{{line-height:1.65;color:#bfd0e6}}a{{color:#9bdcff;text-decoration:none}}a:hover{{text-decoration:underline}}.actions{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}}.btn{{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line2);border-radius:14px;padding:11px 14px;background:rgba(255,255,255,.06);color:var(--text);font-weight:700}}.btn.primary{{background:linear-gradient(135deg,#4db8ff,#277eff);border-color:rgba(77,184,255,.38)}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}.stat{{padding:16px;border-radius:18px;background:rgba(255,255,255,.045);border:1px solid var(--line)}}.stat strong{{display:block;margin-top:7px;line-height:1.45}}.pill{{display:inline-flex;padding:8px 11px;border-radius:999px;border:1px solid var(--line2);background:rgba(255,255,255,.06);font-size:12px;font-weight:700}}.critical,.high{{color:var(--red)}}.medium,.warning{{color:var(--yellow)}}.resolved,.simulated{{color:var(--green)}}.markdown{{display:grid;gap:16px}}.md-section{{padding:20px;border-radius:22px;background:rgba(255,255,255,.04);border:1px solid var(--line)}}.md-section h2{{font-size:22px}}ul{{margin:10px 0 0;padding-left:20px;color:#c6d7ef;line-height:1.8}}li{{margin:4px 0}}code{{font-family:Consolas,"Cascadia Code",monospace;background:rgba(77,184,255,.1);border:1px solid rgba(77,184,255,.14);border-radius:8px;padding:2px 6px;color:#dff3ff}}.empty{{padding:22px;border:1px dashed var(--line2);border-radius:20px;color:var(--muted);text-align:center}}.path{{word-break:break-all;color:var(--muted);font-family:Consolas,"Cascadia Code",monospace;font-size:12px}}@media(max-width:900px){{.shell{{padding:18px 12px 40px}}.hero,.grid{{grid-template-columns:1fr}}.hero-main,.side,.content{{padding:20px}}}}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="panel hero-main">
        <div class="eyebrow">{escape(eyebrow)}</div>
        <h1>{escape(str(service))}</h1>
        <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px">
          <span class="pill {escape(str(severity).lower())}">{escape(str(severity).upper())}</span>
          <span class="pill {escape(str(status).lower())}">{escape(str(status).replace("_", " ").title())}</span>
          <span class="pill">{escape(str(incident_type).replace("_", " "))}</span>
          <span class="pill">{escape(incident_id)}</span>
        </div>
        <p>{escape(str(summary))}</p>
        <div class="actions">
          <a class="btn primary" href="/">Open Dashboard</a>
          <a class="btn" href="/api/incidents/{escape(incident_id)}">Incident JSON</a>
          <a class="btn" href="/postmortems/{escape(incident_id)}">Post-Mortem</a>
          <a class="btn" href="/codefixes/{escape(incident_id)}">Code Fix</a>
          <a class="btn" href="/api/logs?service={escape(str(service))}&limit=100&since_minutes=60">Service Logs</a>
        </div>
      </div>
      <aside class="panel side">
        <div class="eyebrow">Incident Snapshot</div>
        <div class="grid" style="margin-top:14px">
          <div class="stat"><div class="label">Root Cause</div><strong>{escape(str(hypothesis.get("root_cause", "Unknown")))}</strong></div>
          <div class="stat"><div class="label">Confidence</div><strong>{escape(str(verification.get("confidence", hypothesis.get("confidence", "N/A"))))}</strong></div>
          <div class="stat"><div class="label">Remediation</div><strong>{escape(str(remediation.get("status", "not available")).replace("_", " ").title())}</strong></div>
          <div class="stat"><div class="label">Escalate</div><strong>{"Yes" if state.get("escalate_to_human") else "No"}</strong></div>
        </div>
        <p class="path" style="margin-top:16px">{escape(str(artifact_path))}</p>
      </aside>
    </section>
    <section class="panel content">
      <div class="eyebrow">{escape(artifact_label)}</div>
      <div class="markdown" style="margin-top:16px">{rendered_content}</div>
    </section>
  </main>
</body>
</html>"""


def render_artifact_markdown(content: str) -> str:
    sections: list[tuple[str, list[str]]] = []
    current_title = "Post-Mortem"
    current_lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            # Save previous section before overwriting title (skip if empty)
            if current_lines and any(l.strip() for l in current_lines):
                sections.append((current_title, current_lines))
            current_lines = []
            current_title = line[2:].strip()
            continue
        if line.startswith("## "):
            if current_lines and any(l.strip() for l in current_lines):
                sections.append((current_title, current_lines))
            current_title = line[3:].strip()
            current_lines = []
            continue
        current_lines.append(line)
    if current_lines and any(l.strip() for l in current_lines):
        sections.append((current_title, current_lines))

    html_sections = []
    for title, lines in sections:
        body = render_postmortem_lines(lines)
        html_sections.append(f"<article class=\"md-section\"><h2>{escape(title)}</h2>{body}</article>")
    return "".join(html_sections)


def render_postmortem_lines(lines: list[str]) -> str:
    html_parts: list[str] = []
    list_items: list[str] = []
    paragraphs: list[str] = []

    def flush_paragraphs() -> None:
        if paragraphs:
            html_parts.append(f"<p>{escape(' '.join(paragraphs))}</p>")
            paragraphs.clear()

    def flush_list() -> None:
        if list_items:
            html_parts.append("<ul>" + "".join(f"<li>{format_inline_markdown(item)}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    for line in lines:
        if not line.strip():
            flush_paragraphs()
            flush_list()
            continue
        if line.startswith("- "):
            flush_paragraphs()
            list_items.append(line[2:].strip())
            continue
        flush_list()
        paragraphs.append(line.strip())

    flush_paragraphs()
    flush_list()
    return "".join(html_parts) or "<p>No details recorded.</p>"


def format_inline_markdown(value: str) -> str:
    escaped = escape(value)
    parts = escaped.split("`")
    for index in range(1, len(parts), 2):
        parts[index] = f"<code>{parts[index]}</code>"
    return "".join(parts)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
