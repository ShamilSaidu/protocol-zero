"""Tests for demo-facing Redis and Loki integrations."""

from __future__ import annotations

from monitoring.metrics_collector import MetricsCollector
from integrations.loki_client import LokiClient
from integrations.redis_store import RedisEventStore
from integrations.slack_notifier import SlackNotifier


class FakeLokiHttpClient:
    def __init__(self, payload: dict | None = None, ready_status: int = 200) -> None:
        self.payload = payload or {
            "data": {
                "result": [
                    {
                        "stream": {"app": "cartservice", "namespace": "default"},
                        "values": [
                            ["200", "second line"],
                            ["300", "latest line"],
                        ],
                    }
                ]
            }
        }
        self.ready_status = ready_status

    def get(self, url: str, params: dict | None = None):
        if url.endswith("/ready"):
            return FakeResponse({}, self.ready_status)
        return FakeResponse(self.payload, 200)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSlackHttpClient:
    def __init__(self) -> None:
        self.posts = []

    def post(self, url: str, json: dict):
        self.posts.append({"url": url, "json": json})
        return FakeResponse({}, 200)


class FakePrometheusClient:
    def __init__(self, result: list[dict] | Exception) -> None:
        self.result = result

    def custom_query(self, query: str):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_redis_event_store_falls_back_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = RedisEventStore(redis_url="", client=None)

    store.record_event("demo", "Created an event.", {"source": "test"})
    events = store.list_events(limit=5)

    assert store.backend() == "memory"
    assert len(events) == 1
    assert events[0]["type"] == "demo"
    assert events[0]["details"]["source"] == "test"


def test_loki_client_parses_recent_logs() -> None:
    client = LokiClient(base_url="http://localhost:3100", namespace="default", client=FakeLokiHttpClient())

    payload = client.query_logs(service="cartservice", limit=10, since_minutes=5)

    assert payload["available"] is True
    assert payload["query"] == '{namespace="default",app="cartservice"}'
    assert [item["line"] for item in payload["logs"]] == ["latest line", "second line"]


def test_metrics_collector_status_reports_prometheus_health() -> None:
    collector = MetricsCollector(prometheus_url="http://localhost:9090", namespace="default")
    collector.client = FakePrometheusClient([{"metric": {"job": "prometheus"}, "value": [0, "1"]}])

    status = collector.status()

    assert status["configured"] is True
    assert status["available"] is True
    assert status["base_url"] == "http://localhost:9090"


def test_slack_notifier_sends_detection_block_kit_payload() -> None:
    client = FakeSlackHttpClient()
    notifier = SlackNotifier(webhook_url="https://hooks.slack.test/services/demo", client=client)

    result = notifier.notify_detection(
        {
            "incident_id": "INC-SLACK-001",
            "type": "pod_restart_loop",
            "severity": "critical",
            "service_affected": "cartservice",
            "pod": "cartservice-abc123-xyz",
            "detected_at": "2026-05-07T12:00:00+00:00",
            "error_message": "Pod restarted 5 times",
            "alert_name": "PodRestartLoop",
            "namespace": "default",
        }
    )

    assert result == {"sent": True, "incident_id": "INC-SLACK-001"}
    assert client.posts[0]["url"] == "https://hooks.slack.test/services/demo"
    payload = client.posts[0]["json"]
    assert payload["blocks"][0]["type"] == "header"
    assert payload["blocks"][1]["type"] == "section"
    assert payload["blocks"][4]["type"] == "actions"
    assert [button["text"]["text"] for button in payload["blocks"][4]["elements"]] == [
        "Open Protocol Zero",
        "Full Logs",
        "Grafana Logs",
        "Prometheus",
    ]
    assert "INC-SLACK-001" in payload["text"]


def test_slack_notifier_sends_lifecycle_payload_with_artifact_buttons() -> None:
    client = FakeSlackHttpClient()
    notifier = SlackNotifier(webhook_url="https://hooks.slack.test/services/demo", client=client)

    result = notifier.notify_lifecycle_complete(
        {
            "payload": {
                "incident_id": "INC-SLACK-003",
                "type": "pod_restart_loop",
                "severity": "critical",
                "service_affected": "cartservice",
                "error_message": "Pod restarted 5 times",
            },
            "state": {
                "status": "simulated",
                "summary": "Root cause isolated.",
                "selected_hypothesis": {"root_cause": "Runtime health issue", "confidence": 0.81},
                "verification": {"confidence": 0.81},
                "remediation": {"status": "dry_run", "summary": "Restart the failing pod."},
                "postmortem": {"path": "post_mortems/INC-SLACK-003.md"},
            },
        }
    )

    assert result == {"sent": True, "incident_id": "INC-SLACK-003"}
    payload = client.posts[0]["json"]
    action_blocks = [block for block in payload["blocks"] if block["type"] == "actions"]
    assert action_blocks
    assert [button["text"]["text"] for button in action_blocks[0]["elements"]] == [
        "Open Protocol Zero",
        "Post-Mortem",
        "Grafana Dashboard",
        "Grafana Logs",
        "Prometheus",
    ]


def test_slack_notifier_skips_when_webhook_missing() -> None:
    notifier = SlackNotifier(webhook_url="", client=FakeSlackHttpClient())

    result = notifier.notify_detection({"incident_id": "INC-SLACK-002"})

    assert result == {"sent": False, "reason": "not_configured", "incident_id": "INC-SLACK-002"}
