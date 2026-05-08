"""Slack incoming-webhook notifications with Block Kit payloads."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlencode

import httpx


class SlackNotifier:
    """Sends incident lifecycle notifications to a Slack incoming webhook."""

    def __init__(
        self,
        webhook_url: str | None = None,
        enabled: bool | None = None,
        client: Any | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.webhook_url = webhook_url if webhook_url is not None else os.getenv("SLACK_WEBHOOK_URL", "")
        if enabled is None:
            enabled = os.getenv("SLACK_NOTIFICATIONS_ENABLED", "true").lower() == "true"
        self.enabled = enabled
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.protocol_zero_url = self._clean_base_url(os.getenv("PROTOCOL_ZERO_PUBLIC_URL", "http://localhost:8000"))
        self.grafana_url = self._clean_base_url(os.getenv("GRAFANA_URL", "http://localhost:3000"))
        self.grafana_dashboard_url = os.getenv(
            "GRAFANA_DASHBOARD_URL",
            f"{self.grafana_url}/d/protocol-zero-demo/protocol-zero-demo",
        )
        self.prometheus_url = self._clean_base_url(os.getenv("PROMETHEUS_URL", "http://localhost:9090"))

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def status(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "configured": self.is_configured()}

    def notify_detection(self, incident: dict[str, Any]) -> dict[str, Any]:
        return self._post(self._build_detection_payload(incident), incident.get("incident_id"))

    def notify_lifecycle_complete(self, persisted_incident: dict[str, Any]) -> dict[str, Any]:
        state = persisted_incident.get("state", {})
        incident = persisted_incident.get("payload", persisted_incident)
        return self._post(self._build_lifecycle_payload(incident, state), incident.get("incident_id"))

    def _post(self, payload: dict[str, Any], incident_id: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"sent": False, "reason": "disabled", "incident_id": incident_id}
        if not self.webhook_url:
            return {"sent": False, "reason": "not_configured", "incident_id": incident_id}
        response = self.client.post(self.webhook_url, json=payload)
        response.raise_for_status()
        return {"sent": True, "incident_id": incident_id}

    def _build_detection_payload(self, incident: dict[str, Any]) -> dict[str, Any]:
        incident_id = self._text(incident.get("incident_id"), "INC-UNKNOWN")
        service = self._text(incident.get("service_affected"), "unknown-service")
        severity = self._text(incident.get("severity"), "unknown")
        incident_type = self._text(incident.get("type"), "unknown")
        message = self._text(incident.get("error_message"), "No error message provided.")
        alert_name = self._text(incident.get("alert_name"), incident_type)
        namespace = self._text(incident.get("namespace"), "default")
        detected_at = self._text(incident.get("detected_at"), "unknown")
        color_label = self._severity_label(severity)
        header = f"{color_label} {severity.upper()} detection"
        return {
            "text": f"{severity.upper()} detection for {service} ({incident_id})",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": header, "emoji": True}},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*{self._slack_escape(service)}* · `{self._slack_escape(alert_name)}` · `{self._slack_escape(namespace)}`",
                        }
                    ],
                },
                {"type": "divider"},
                self._section_heading("Incident Snapshot"),
                {
                    "type": "section",
                    "fields": [
                        self._mrkdwn_field("*Incident ID*", incident_id),
                        self._mrkdwn_field("*Type*", incident_type),
                        self._mrkdwn_field("*Detected at*", detected_at),
                        self._mrkdwn_field("*Source*", self._text(incident.get("source"), "manual")),
                    ],
                },
                {"type": "divider"},
                self._section_heading("Signal"),
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Signal*\n{self._slack_escape(message)}"}},
                self._actions_block(
                    [
                        self._button("Open Protocol Zero", self._incident_url(incident_id), "primary", "open_protocol_zero"),
                        self._button("Full Logs", self._api_logs_url(service), None, "open_protocol_zero_logs"),
                        self._button("Grafana Logs", self._grafana_explore_url(service), None, "open_grafana_logs"),
                        self._button("Prometheus", self._prometheus_query_url(service), None, "open_prometheus"),
                    ]
                ),
                self._footer("Protocol Zero detection pipeline"),
            ],
        }

    def _build_lifecycle_payload(self, incident: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        incident_id = self._text(incident.get("incident_id"), "INC-UNKNOWN")
        service = self._text(incident.get("service_affected"), "unknown-service")
        status = self._text(state.get("status"), "unknown")
        severity = self._text(incident.get("severity"), "unknown")
        summary = self._text(state.get("summary") or incident.get("error_message"), "No summary available.")
        hypothesis = state.get("selected_hypothesis", {})
        verification = state.get("verification", {})
        remediation = state.get("remediation", {})
        code_fix = state.get("code_fix", {})
        postmortem = state.get("postmortem", {})
        header = f"Protocol Zero completed: {service} is {status}"
        fields = [
            self._mrkdwn_field("*Incident ID*", incident_id),
            self._mrkdwn_field("*Severity*", severity),
            self._mrkdwn_field("*Root cause*", self._text(hypothesis.get("root_cause"), "Unknown")),
            self._mrkdwn_field("*Confidence*", str(verification.get("confidence", hypothesis.get("confidence", "N/A")))),
            self._mrkdwn_field("*Remediation*", self._text(remediation.get("status"), "not available")),
            self._mrkdwn_field("*Escalate*", "yes" if state.get("escalate_to_human") else "no"),
        ]
        artifact_buttons = self._artifact_buttons(incident_id, code_fix, postmortem)
        blocks: list[dict[str, Any]] = [
            {"type": "header", "text": {"type": "plain_text", "text": "Protocol Zero diagnosis", "emoji": True}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*{self._slack_escape(service)}* · `{self._slack_escape(status)}` · `{self._slack_escape(incident_id)}`",
                    }
                ],
            },
            {"type": "divider"},
            self._section_heading("Outcome"),
            {"type": "section", "fields": fields},
            {"type": "divider"},
            self._section_heading("Summary"),
            {"type": "section", "text": {"type": "mrkdwn", "text": self._slack_escape(summary)}},
        ]
        remediation_summary = remediation.get("summary")
        if remediation_summary:
            blocks.extend([{"type": "divider"}, self._section_heading("Remediation")])
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": self._slack_escape(remediation_summary)},
                }
            )
        blocks.append({"type": "divider"})
        blocks.append(
            self._actions_block(
                [
                    self._button("Open Protocol Zero", self._incident_url(incident_id), "primary", "open_protocol_zero"),
                    *artifact_buttons,
                    self._button("Grafana Dashboard", self.grafana_dashboard_url, None, "open_grafana_dashboard"),
                    self._button("Grafana Logs", self._grafana_explore_url(service), None, "open_grafana_logs"),
                ]
            )
        )
        blocks.append(self._footer("Protocol Zero incident lifecycle"))
        return {"text": f"{header} ({incident_id})", "attachments": [{"color": "#FF4D4D", "blocks": blocks}]}

    def _artifact_buttons(self, incident_id: str, code_fix: dict[str, Any], postmortem: dict[str, Any]) -> list[dict[str, Any]]:
        buttons = []
        if code_fix.get("artifact_path"):
            buttons.append(self._button("Code Fix", self._codefix_url(incident_id), None, "open_code_fix"))
        if postmortem.get("path"):
            buttons.append(self._button("Post-Mortem", self._postmortem_url(incident_id), None, "open_postmortem"))
        return buttons

    def _incident_url(self, incident_id: str) -> str:
        return f"{self.protocol_zero_url}/?incident={quote(incident_id)}"

    def _postmortem_url(self, incident_id: str) -> str:
        return f"{self.protocol_zero_url}/postmortems/{quote(incident_id)}"

    def _codefix_url(self, incident_id: str) -> str:
        return f"{self.protocol_zero_url}/codefixes/{quote(incident_id)}"

    def _api_logs_url(self, service: str) -> str:
        params = urlencode({"service": service, "limit": 100, "since_minutes": 60})
        return f"{self.protocol_zero_url}/api/logs?{params}"

    def _prometheus_query_url(self, service: str) -> str:
        query = f'up{{job=~".*{service}.*"}}'
        return f"{self.prometheus_url}/graph?g0.expr={quote(query)}&g0.tab=1"

    def _grafana_explore_url(self, service: str) -> str:
        query = quote(f'{{namespace="default",app="{service}"}}')
        return f"{self.grafana_url}/explore?left=%7B%22queries%22:%5B%7B%22expr%22:%22{query}%22%7D%5D%7D"

    def _actions_block(self, buttons: list[dict[str, Any]]) -> dict[str, Any]:
        return {"type": "actions", "elements": [button for button in buttons if button.get("url")][:5]}

    @staticmethod
    def _section_heading(text: str) -> dict[str, Any]:
        return {"type": "section", "text": {"type": "mrkdwn", "text": f"*{text}*"}}

    @staticmethod
    def _footer(text: str) -> dict[str, Any]:
        return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}

    @staticmethod
    def _button(label: str, url: str, style: str | None, action_id: str) -> dict[str, Any]:
        button = {
            "type": "button",
            "text": {"type": "plain_text", "text": label, "emoji": True},
            "url": url,
            "action_id": action_id,
        }
        if style:
            button["style"] = style
        return button

    @staticmethod
    def _clean_base_url(url: str) -> str:
        return url.rstrip("/")

    @staticmethod
    def _incident_id_from_path(path: str) -> str:
        name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
        return name[:-3] if name.endswith(".md") else name

    @staticmethod
    def _mrkdwn_field(label: str, value: str) -> dict[str, Any]:
        return {"type": "mrkdwn", "text": f"{label}\n{SlackNotifier._slack_escape(value)}"}

    @staticmethod
    def _severity_label(severity: str) -> str:
        normalized = severity.lower()
        if normalized in {"critical", "high"}:
            return ":rotating_light:"
        if normalized in {"warning", "medium"}:
            return ":warning:"
        return ":information_source:"

    @staticmethod
    def _text(value: Any, default: str) -> str:
        if value is None:
            return default
        text = str(value)
        return text if text else default

    @staticmethod
    def _slack_escape(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
