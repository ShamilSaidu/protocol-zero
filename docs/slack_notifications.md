# Slack Notifications

Protocol Zero can send incident notifications to a Slack channel through a Slack incoming webhook. The messages use Slack Block Kit so responders get a compact incident card with status, context, and buttons that jump directly into Protocol Zero, Grafana, Prometheus, logs, and generated post-mortem output.

## What This Feature Does

Slack notifications are sent for two major points in the incident lifecycle:

1. Detection notification
   - Sent as soon as Protocol Zero accepts a detected or manually triggered incident.
   - Shows severity, service, incident type, detection time, source, and signal/error text.
   - Includes buttons for Protocol Zero, Protocol Zero log API, Grafana logs, and Prometheus.

2. Lifecycle completion notification
   - Sent after investigation, correlation, verification, remediation planning, code-fix artifact generation, and post-mortem generation finish.
   - Shows final status, severity, selected root cause, confidence, remediation status, escalation decision, summary, remediation detail, and artifact paths.
   - Includes buttons for Protocol Zero, post-mortem API, Grafana dashboard, Grafana logs, and Prometheus.

This is meant to make Slack the first alert surface while keeping the full investigation inside Protocol Zero and the observability tools.

## How It Works

The integration lives in:

- `integrations/slack_notifier.py`
- `orchestrator/runtime.py`

The runtime creates one `SlackNotifier` instance when `ProtocolZeroRuntime` starts. During incident processing:

1. `ProtocolZeroRuntime.process_incident()` stores the initial incident state.
2. It calls `SlackNotifier.notify_detection()` to send the detection card.
3. The LangGraph workflow investigates the incident, selects a hypothesis, verifies confidence, plans remediation, generates code-fix output, and writes a post-mortem.
4. The runtime saves the final state.
5. It calls `SlackNotifier.notify_lifecycle_complete()` to send the completion card.

When detection is run with `auto_process=false`, Protocol Zero still sends the detection notification, but it does not send a completion notification because the orchestration flow has not run.

Slack failures do not break incident processing. If the webhook request fails, Protocol Zero records a `slack_notification_failed` event in the existing event stream and continues the incident workflow.

## Slack Message Buttons

The Slack cards use URL buttons because the current implementation uses incoming webhooks. Incoming webhooks can post Block Kit messages, but they cannot receive button-click callbacks by themselves.

Current button behavior:

- `Open Protocol Zero`: opens the Protocol Zero dashboard with the incident ID in the query string.
- `Full Logs`: opens Protocol Zero's `/api/logs` endpoint for the affected service.
- `Grafana Logs`: opens Grafana Explore with a service-focused Loki query.
- `Grafana Dashboard`: opens the Protocol Zero Grafana dashboard.
- `Prometheus`: opens Prometheus with a service-focused query.
- `Post-Mortem`: opens the Protocol Zero post-mortem API endpoint for the incident.

If we later need buttons such as `Acknowledge`, `Escalate`, `Assign to me`, or `Run remediation`, we should create a full Slack app with interactivity enabled. That would require a public callback URL, Slack signing-secret validation, and FastAPI endpoints to handle Slack actions.

## Environment Variables

Add these values to `.env`:

```env
SLACK_NOTIFICATIONS_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/workspace/webhook
PROTOCOL_ZERO_PUBLIC_URL=http://localhost:8000
GRAFANA_URL=http://localhost:3000
GRAFANA_DASHBOARD_URL=http://localhost:3000/d/protocol-zero-demo/protocol-zero-demo
```

Existing monitoring variables are also used:

```env
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100
```

Variable details:

- `SLACK_NOTIFICATIONS_ENABLED`: set to `true` to send notifications, or `false` to disable Slack without removing the webhook.
- `SLACK_WEBHOOK_URL`: Slack incoming webhook URL for the channel that should receive incident alerts.
- `PROTOCOL_ZERO_PUBLIC_URL`: base URL that Slack buttons should use for the Protocol Zero dashboard/API.
- `GRAFANA_URL`: base URL for Grafana.
- `GRAFANA_DASHBOARD_URL`: direct dashboard URL for the Protocol Zero Grafana dashboard.
- `PROMETHEUS_URL`: base URL for Prometheus. This is already used elsewhere by Protocol Zero.

For local demos, `localhost` URLs are fine if Slack is opened on the same machine running the port-forwards. For shared environments, use URLs that other teammates can access, such as a VM hostname, internal DNS name, reverse proxy, or tunnel URL.

## Creating a Slack Webhook

Each developer or deployment environment should create its own webhook. Do not commit real webhook URLs.

1. Open https://api.slack.com/apps.
2. Click `Create New App`.
3. Choose `From scratch`.
4. Select the Slack workspace.
5. Open `Incoming Webhooks`.
6. Turn `Activate Incoming Webhooks` on.
7. Click `Add New Webhook to Workspace`.
8. Pick the channel where Protocol Zero should post.
9. Copy the webhook URL.
10. Paste it into `.env` as `SLACK_WEBHOOK_URL`.

The webhook URL is a secret. Anyone with the URL can post to the selected Slack channel. Rotate it in Slack if it is exposed in chat, logs, screenshots, or commits.

## Setup After Pulling This Repo

After someone pulls this feature from GitHub, they need to do this locally:

1. Pull the latest code.

```powershell
git pull
```

2. Install dependencies if needed.

```powershell
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt
```

3. Copy or update the env file.

```powershell
Copy-Item .env.example .env
notepad .env
```

4. Add their own Slack webhook URL.

```env
SLACK_NOTIFICATIONS_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

5. Make sure local observability URLs match their setup.

```env
PROTOCOL_ZERO_PUBLIC_URL=http://localhost:8000
GRAFANA_URL=http://localhost:3000
GRAFANA_DASHBOARD_URL=http://localhost:3000/d/protocol-zero-demo/protocol-zero-demo
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100
```

6. Restart Protocol Zero after changing `.env`.

```powershell
.\.venv311\Scripts\python.exe main.py
```

## Testing Slack Only

Use this command to verify the webhook without running the full incident lifecycle:

```powershell
.\.venv311\Scripts\python.exe -c "from dotenv import load_dotenv; load_dotenv(); from integrations.slack_notifier import SlackNotifier; print(SlackNotifier().notify_detection({'incident_id':'INC-SLACK-TEST','type':'manual_test','severity':'high','service_affected':'protocol-zero','detected_at':'2026-05-08T00:00:00Z','error_message':'Slack webhook test from Protocol Zero','alert_name':'SlackWebhookTest','namespace':'default','source':'test'}))"
```

Expected terminal output:

```text
{'sent': True, 'incident_id': 'INC-SLACK-TEST'}
```

Expected Slack result:

- a detection card appears in the configured channel
- the card has action buttons
- the `Open Protocol Zero`, `Full Logs`, `Grafana Logs`, and `Prometheus` buttons render

## Testing the Full Incident Flow

Start Protocol Zero:

```powershell
.\.venv311\Scripts\python.exe main.py
```

Trigger a manual incident:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/incidents/trigger" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"service":"cartservice","incident_type":"pod_restart_loop","severity":"critical","error_message":"Manual Slack notification test"}'
```

Expected Slack result:

1. A detection card appears immediately.
2. A completion card appears after Protocol Zero finishes investigation, remediation planning, code-fix generation, and post-mortem generation.

## Troubleshooting

If no Slack message appears:

- confirm `SLACK_NOTIFICATIONS_ENABLED=true`
- confirm `SLACK_WEBHOOK_URL` is present in `.env`
- restart Protocol Zero after editing `.env`
- verify the webhook still exists in Slack
- check `/api/events` for `slack_notification_failed`

If buttons open the wrong place:

- update `PROTOCOL_ZERO_PUBLIC_URL`
- update `GRAFANA_URL`
- update `GRAFANA_DASHBOARD_URL`
- update `PROMETHEUS_URL`
- restart Protocol Zero

If Slack returns an error:

- make sure the webhook URL was copied completely
- create a fresh webhook if the old one was revoked
- rotate the webhook if it was pasted into chat or committed

If teammates cannot open `localhost` links:

- replace local URLs with shared URLs they can reach
- use an internal host, reverse proxy, or tunnel for demos
- keep the port-forwards running if using local Kubernetes tools

## Security Notes

- Never commit `.env`.
- Never commit a real `SLACK_WEBHOOK_URL`.
- Use `.env.example` only for placeholders.
- Rotate webhook URLs if they are exposed.
- Use a dedicated Slack channel for demo alerts if testing creates noisy notifications.
