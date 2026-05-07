# Protocol Zero

Protocol Zero is an autonomous SRE incident-response MVP for a Kubernetes microservice environment. It detects failures from observability data, runs multi-agent investigation, correlates a likely root cause, proposes or executes remediation, generates code-fix artifacts, and writes post-mortems.

## What this MVP does

- detects incidents from Prometheus metrics
- runs investigation, developer, and devops agents in parallel
- correlates findings into a root-cause hypothesis
- applies verification and safety thresholds before remediation
- supports dry-run and live remediation modes
- generates a code-fix artifact and optional GitHub PR
- writes a post-mortem for each processed incident
- sends optional Slack Block Kit notifications through an incoming webhook
- exposes a FastAPI API and dashboard

## Project structure

- `monitoring/`: Prometheus collection and incident detection
- `agents/`: investigation, developer, and devops agents
- `orchestrator/`: correlation, verification, LangGraph workflow, runtime
- `remediation/`: safety-aware remediation engine
- `post_mortem/`: markdown post-mortem generation
- `database/`: PostgreSQL-first persistence with SQLite fallback
- `frontend/`: dashboard UI
- `scripts/`: smoke tests, dashboard provisioning, chaos tooling, startup helper
- `docs/`: demo notes and supplemental documentation

## Recommended environment

This repo is developed and verified on Windows PowerShell with:

- Python `3.11.9` (64-bit)
- Docker Desktop running Linux containers
- Minikube using the Docker driver
- `kubectl`
- Helm `3.19.x`
- PostgreSQL 15 and Redis 7 via Docker containers

## 1. Install prerequisites

Install these tools first:

1. Docker Desktop
2. Python 3.11 (64-bit)
3. Minikube
4. `kubectl`
5. Helm 3
6. Git

Recommended configuration:

- Docker Desktop must be running before starting Minikube
- Minikube should use the Docker driver
- Helm 4 is not recommended for this repo

Verify your installs:

```powershell
docker --version
py -3.11 --version
minikube version
kubectl version --client
helm version
git --version
```

## 2. Clone the repo

```powershell
git clone https://github.com/ShamilSaidu/protocol-zero.git
cd protocol-zero
```

## 3. Create the Python environment

Create a fresh virtual environment with Python 3.11:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If activation or `venv` executables ever behave strangely after changing Python installs, recreate the venv with the same commands above.

## 4. Create the environment file

Copy the template and fill in real values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Required values:

- `GROQ_API_KEY`
- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/protocol_zero`
- `REDIS_URL=redis://localhost:6379`
- `PROMETHEUS_URL=http://localhost:9090`
- `LOKI_URL=http://localhost:3100`
- `SLACK_WEBHOOK_URL` if Slack notifications should be enabled

Recommended safe demo values:

```env
DRY_RUN_MODE=true
ALLOW_GITHUB_WRITE=false
ENABLE_BACKGROUND_DETECTOR=false
SLACK_NOTIFICATIONS_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/workspace/webhook
PROTOCOL_ZERO_PUBLIC_URL=http://localhost:8000
GRAFANA_URL=http://localhost:3000
GRAFANA_DASHBOARD_URL=http://localhost:3000/d/protocol-zero-demo/protocol-zero-demo
```

Slack setup notes:

- create a Slack incoming webhook for the channel that should receive incident notifications
- put the real webhook URL only in `.env`
- do not commit `.env` or a real Slack webhook URL
- after pulling this repo, each developer must create or provide their own webhook URL
- see [docs/slack_notifications.md](docs/slack_notifications.md) for the full setup, testing flow, button behavior, and troubleshooting guide

## 5. Start PostgreSQL and Redis

Create the containers once:

```powershell
docker run --name protocol-zero-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=protocol_zero -p 5432:5432 -d postgres:15
docker run --name protocol-zero-redis -p 6379:6379 -d redis:7-alpine
```

On later runs, just start them:

```powershell
docker start protocol-zero-db
docker start protocol-zero-redis
```

Verify:

```powershell
docker ps
```

## 6. Start Minikube

```powershell
minikube start --memory=6144 --cpus=3 --driver=docker
kubectl get nodes
```

Expected result:
- the node named `minikube` is `Ready`

## 7. Deploy the sample microservices app

If the sample app is not present locally, pull it into the repo root exactly as expected by this project:

```powershell
git clone https://github.com/GoogleCloudPlatform/microservices-demo.git sample-app
```

Deploy the app:

```powershell
kubectl apply -f .\sample-app\release\kubernetes-manifests.yaml
kubectl wait --for=condition=Available --timeout=10m deployment/frontend
kubectl wait --for=condition=Available --timeout=10m deployment/cartservice
kubectl wait --for=condition=Available --timeout=10m deployment/checkoutservice
```

Check pods:

```powershell
kubectl get pods
```

## 8. Install Prometheus, Grafana, Loki, and Promtail

Add the Helm repos:

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

Install the Prometheus and Grafana stack:

```powershell
helm install prometheus prometheus-community/kube-prometheus-stack `
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false `
  --set grafana.adminPassword=admin123
```

Install Loki and Promtail:

```powershell
helm install loki grafana/loki-stack `
  --set grafana.enabled=false `
  --set promtail.enabled=true
```

Check pods again:

```powershell
kubectl get pods
```

You should see healthy pods for:

- `prometheus-grafana`
- `prometheus-prometheus-kube-prometheus-prometheus-0`
- `loki-0`
- `loki-promtail-*`

## 9. Start the port-forwards

Open four separate PowerShell windows.

Window 1:

```powershell
kubectl port-forward svc/frontend 8080:80
```

Window 2:

```powershell
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Window 3:

```powershell
kubectl port-forward svc/prometheus-grafana 3000:80
```

Window 4:

```powershell
kubectl port-forward svc/loki 3100:3100
```

Optional helper:

```powershell
.\start_protocol_zero.ps1
```

## 10. Run smoke checks

Groq API smoke test:

```powershell
python scripts\test_groq.py
```

Prometheus smoke test:

```powershell
python scripts\test_prometheus.py
```

Unit and end-to-end tests:

```powershell
pytest tests -v
```

## 11. Start Protocol Zero

```powershell
python main.py
```

Open these pages:

- `http://localhost:8000`
- `http://localhost:8000/docs`
- `http://localhost:8000/health`
- `http://localhost:8080`
- `http://localhost:9090`
- `http://localhost:3000`

Health should report:
- `status: healthy`
- namespace `default`
- PostgreSQL database URL

## 12. Provision the Grafana demo dashboard

Import the ready-made dashboard into Grafana:

```powershell
.\scripts\provision_grafana_demo_dashboard.ps1
```

Open Grafana:

- URL: `http://localhost:3000`
- username: `admin`
- password: `admin123`

Then open the dashboard:

- `Protocol Zero Demo`
- direct path: `http://localhost:3000/d/protocol-zero-demo/protocol-zero-demo`

This dashboard shows:

- active scrape targets
- total restarts
- active pods
- Grafana health
- CPU usage by pod
- memory working set by pod
- restart count by pod
- live Loki logs from the cluster

## 13. Prometheus and Grafana live queries

Prometheus shows `No data queried yet` until you enter a query. That is normal.

Use these queries in Prometheus or Grafana Explore.

Basic target health:

```promql
up
```

CPU by pod:

```promql
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="default",pod!=""}[5m]))
```

Memory by pod in MiB:

```promql
sum by (pod) (container_memory_working_set_bytes{namespace="default",pod!=""}) / 1024 / 1024
```

Restart counts:

```promql
sum by (pod) (kube_pod_container_status_restarts_total{namespace="default"})
```

For logs in Grafana Explore, switch datasource to `Loki` and use:

```logql
{namespace="default"}
```

To focus on one service:

```logql
{namespace="default", app="cartservice"}
```

## 14. Recommended live demo flow

Keep these browser tabs ready:

- `http://localhost:8080`
- `http://localhost:9090`
- `http://localhost:3000`
- `http://localhost:8000`
- `http://localhost:8000/docs`

### Part A: Show the environment

1. Open Online Boutique at `http://localhost:8080`
2. Open Prometheus and run `up`
3. Open Grafana and show the `Protocol Zero Demo` dashboard
4. Point out the live Loki logs panel
5. Open the Protocol Zero dashboard at `http://localhost:8000`

### Part B: Show the guaranteed end-to-end workflow

In the Protocol Zero dashboard:

- service: `cartservice`
- incident type: `pod_restart_loop`
- severity: `critical`
- click `Trigger and Process`

Equivalent API call:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/incidents/trigger" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"service":"cartservice","incident_type":"pod_restart_loop","severity":"critical"}'
```

Expected result:

- an incident is created
- specialized agents investigate in parallel
- the orchestrator selects a likely hypothesis
- remediation is planned in dry-run mode
- a code-fix artifact is generated
- a post-mortem is generated
- the incident appears in the dashboard timeline

### Part C: Show incident detail

Open the incident detail and point out:

- `investigation_findings`
- `selected_hypothesis`
- `verification`
- `remediation`
- `code_fix`
- `postmortem`

## 15. Optional live detection demo

Inject a real fault:

```powershell
.\scripts\chaos.ps1 -Action kill-pod -Service cartservice
```

Then run detection:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/incidents/detect?auto_process=true" -Method POST
```

This demonstrates:

- a real cluster fault
- Protocol Zero detection from observability data
- multi-agent investigation
- reasoning and remediation planning
- generated incident artifacts

## 16. Useful commands

```powershell
python scripts\test_groq.py
python scripts\test_prometheus.py
pytest tests -v
.\scripts\chaos.ps1 -Action kill-pod -Service cartservice
.\scripts\provision_grafana_demo_dashboard.ps1
```

## 17. Troubleshooting

If Grafana panels are empty:

- make sure the Prometheus and Loki port-forwards are still running
- rerun `./scripts/provision_grafana_demo_dashboard.ps1`
- test Prometheus with `up`
- test Loki with `{namespace="default"}`

If Prometheus says `No data queried yet`:

- this is only the initial empty screen
- type a query such as `up` and click `Execute`

If Protocol Zero falls back to SQLite:

- make sure `protocol-zero-db` is running
- restart `python main.py`

If the dashboard is empty:

- trigger a manual incident first
- refresh the page

If the chaos script cannot find a pod:

```powershell
kubectl get pods
```

## 18. Safety model

- `DRY_RUN_MODE=true` keeps remediation non-destructive
- confidence thresholds gate automated action
- GitHub PR creation stays off unless `ALLOW_GITHUB_WRITE=true`
- PostgreSQL is preferred, but the app can fall back to SQLite when needed

## Additional docs

- [docs/demo_runbook.md](docs/demo_runbook.md)
- [docs/mvp_overview.md](docs/mvp_overview.md)
- [scripts/provision_grafana_demo_dashboard.ps1](scripts/provision_grafana_demo_dashboard.ps1)
