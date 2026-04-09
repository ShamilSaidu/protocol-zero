# Protocol Zero End-to-End Demo Runbook

This runbook is the exact Windows PowerShell flow to bring up the full Protocol Zero demo and present it cleanly.

## What the demo shows

By the end of the run, you will be able to show:
- the Online Boutique microservices app running on Minikube
- Prometheus scraping live metrics
- Grafana showing live metrics and live logs through Loki
- the Protocol Zero dashboard and API
- Protocol Zero showing its own Redis-backed activity stream
- Protocol Zero showing recent Loki log lines directly in the dashboard
- a full incident workflow from trigger or detection through investigation, reasoning, remediation, code-fix artifact generation, and post-mortem generation

## Assumptions

This runbook assumes:
- Docker Desktop is running
- Minikube is installed and uses the Docker driver
- Helm 3 is installed
- the repo is located at `C:\Users\shami\OneDrive\Desktop\protocol-zero`
- the Python virtual environment already exists at `venv`
- [C:\Users\shami\OneDrive\Desktop\protocol-zero\.env](C:\Users\shami\OneDrive\Desktop\protocol-zero\.env) contains valid values

Recommended `.env` values for a safe demo:

```env
DRY_RUN_MODE=true
ALLOW_GITHUB_WRITE=false
ENABLE_BACKGROUND_DETECTOR=false
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100
```

## Step 1: Open the repo and activate the venv

```powershell
cd C:\Users\shami\OneDrive\Desktop\protocol-zero
.\venv\Scripts\Activate.ps1
```

## Step 2: Verify local infrastructure

```powershell
docker ps
minikube status
kubectl get nodes
```

If Minikube is not running:

```powershell
minikube start --memory=6144 --cpus=3 --driver=docker
```

## Step 3: Verify the sample app and monitoring stack

```powershell
kubectl get pods
kubectl get deployments
kubectl get svc
```

Healthy demo pods should include:
- `frontend`
- `cartservice`
- `checkoutservice`
- `paymentservice`
- `productcatalogservice`
- `prometheus-grafana`
- `prometheus-prometheus-kube-prometheus-prometheus-0`
- `loki-0`
- `loki-promtail-*`

If the sample app is missing:

```powershell
kubectl apply -f .\sample-app\release\kubernetes-manifests.yaml
kubectl wait --for=condition=Available --timeout=10m deployment/frontend
kubectl wait --for=condition=Available --timeout=10m deployment/cartservice
kubectl wait --for=condition=Available --timeout=10m deployment/checkoutservice
```

## Step 4: Start PostgreSQL and Redis

If the containers already exist, start them:

```powershell
docker start protocol-zero-db
docker start protocol-zero-redis
```

If they do not exist yet, create them once:

```powershell
docker run --name protocol-zero-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=protocol_zero -p 5432:5432 -d postgres:15
docker run --name protocol-zero-redis -p 6379:6379 -d redis:7-alpine
```

Important:
- only use `docker run` once per container name
- after that, use `docker start`

## Step 5: Start the port-forwards

Use separate PowerShell windows for each command.

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

Shortcut option:

```powershell
.\start_protocol_zero.ps1
```

## Step 6: Start Protocol Zero

Open a fresh PowerShell window in the repo and run:

```powershell
cd C:\Users\shami\OneDrive\Desktop\protocol-zero
.\venv\Scripts\Activate.ps1
python main.py
```

Verify these pages:
- `http://localhost:8000`
- `http://localhost:8000/docs`
- `http://localhost:8000/health`
- `http://localhost:8080`
- `http://localhost:9090`
- `http://localhost:3000`

In Protocol Zero itself, you should now see:
- `Redis: Live` when Redis is reachable
- `Loki: Live` when Loki is reachable
- an `Activity Stream` panel fed by Redis
- a `Live Loki Logs` panel that can query logs for a service

Quick API verification:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/stats
Invoke-RestMethod http://localhost:8000/api/events
Invoke-RestMethod "http://localhost:8000/api/logs?service=cartservice&since_minutes=15&limit=20"
```

## Step 7: Provision the Grafana demo dashboard

Run this after the Grafana port-forward is active:

```powershell
.\scripts\provision_grafana_demo_dashboard.ps1
```

Then open Grafana:
- `http://localhost:3000`
- username: `admin`
- password: `admin123`

Open the dashboard named `Protocol Zero Demo`.

What it shows:
- active scrape targets
- restart totals
- active pods
- Grafana health
- CPU usage by pod
- memory working set by pod
- restart count by pod
- live Loki logs from the cluster

## Step 8: Prometheus and Grafana live queries

Prometheus showing `No data queried yet` is normal until you run a query. Use these in the Prometheus expression bar.

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

Grafana Explore can use the same Prometheus queries. For logs, switch the datasource to `Loki` and use:

```logql
{namespace="default"}
```

To focus on one service, for example `cartservice`:

```logql
{namespace="default", app="cartservice"}
```

## Step 9: Recommended demo tabs

Before presenting, keep these open:
- `http://localhost:8080` for the sample app
- `http://localhost:9090` for Prometheus
- `http://localhost:3000` for Grafana
- `http://localhost:8000` for the Protocol Zero dashboard
- `http://localhost:8000/docs` for the API docs

## Step 10: Safest demo flow

### A. Show the environment

1. Open the Online Boutique app at `http://localhost:8080`
2. Open Prometheus and run `up`
3. Open Grafana and show the `Protocol Zero Demo` dashboard
4. Point out the live Loki logs panel
5. Open the Protocol Zero dashboard at `http://localhost:8000`
6. Point out the `Activity Stream` panel and the `Live Loki Logs` panel in Protocol Zero itself

### B. Show the guaranteed end-to-end flow with a manual incident

In the Protocol Zero dashboard:
- service: `cartservice`
- incident type: `pod_restart_loop`
- severity: `critical`
- click `Trigger and Process`

Or use PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/incidents/trigger" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"service":"cartservice","incident_type":"pod_restart_loop","severity":"critical"}'
```

Expected result:
- an incident is created
- multiple investigation agents run
- correlation and reasoning select a likely root cause
- remediation is proposed in dry-run mode
- a code-fix artifact is generated
- a post-mortem is generated
- the activity stream updates with runtime and incident events
- the incident appears in the dashboard timeline

### C. Show the stored incident detail

On the dashboard, click the incident row and point out:
- `investigation_findings`
- `selected_hypothesis`
- `verification`
- `remediation`
- `code_fix`
- `postmortem`

## Step 11: Optional live detection demo

If you want to show a live cluster fault and detection cycle, keep Prometheus, Grafana, Loki, and Protocol Zero running.

Inject a fault:

```powershell
.\scripts\chaos.ps1 -Action kill-pod -Service cartservice
```

Note:
- `kill-pod` is useful for a pod-level failure demonstration.
- If you specifically want a `deployment_unavailable` incident, use:

```powershell
.\scripts\chaos.ps1 -Action deployment-outage -Service cartservice
```

Then run detection:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/incidents/detect?auto_process=true" -Method POST
```

This demonstrates:
- a real cluster fault
- Protocol Zero detection from observability data
- investigation and reasoning
- remediation planning
- generated artifacts after handling

## Step 12: Show generated artifacts on disk

Post-mortems:

```powershell
Get-ChildItem .\post_mortems
Get-Content .\post_mortems\<incident-id>.md
```

Code-fix artifacts:

```powershell
Get-ChildItem .\docs\codefixes
Get-Content .\docs\codefixes\<incident-id>.md
```

## Step 13: Run the demo smoke tests

From the repo root with the virtual environment active:

```powershell
python -m pytest tests\test_api_smoke.py -v
python -m pytest tests\test_integrations.py -v
python -m pytest tests\test_repository.py -v
python -m pytest tests -v
```

## Step 14: Troubleshooting

If Grafana opens but panels are empty:
- make sure the Prometheus and Loki port-forwards are still running
- rerun [C:\Users\shami\OneDrive\Desktop\protocol-zero\scripts\provision_grafana_demo_dashboard.ps1](C:\Users\shami\OneDrive\Desktop\protocol-zero\scripts\provision_grafana_demo_dashboard.ps1)
- open Grafana Explore and test Prometheus with `up`
- open Grafana Explore and test Loki with `{namespace="default"}`

If Prometheus says `No data queried yet`:
- that is only the initial empty screen
- type `up` and press Execute

If Protocol Zero falls back to SQLite:
- make sure `protocol-zero-db` is running
- then restart `python main.py`

If the dashboard is empty:
- trigger a manual incident first
- then refresh the page

If the chaos script cannot find a pod:

```powershell
kubectl get pods
```

Confirm the target service has a running pod.

## Step 15: Shortest repeatable demo path

If you need the shortest reliable setup:

```powershell
cd C:\Users\shami\OneDrive\Desktop\protocol-zero
.\venv\Scripts\Activate.ps1
docker start protocol-zero-db
docker start protocol-zero-redis
python main.py
```

And in separate PowerShell windows:

```powershell
kubectl port-forward svc/frontend 8080:80
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
kubectl port-forward svc/prometheus-grafana 3000:80
kubectl port-forward svc/loki 3100:3100
```

Then:
1. run [C:\Users\shami\OneDrive\Desktop\protocol-zero\scripts\provision_grafana_demo_dashboard.ps1](C:\Users\shami\OneDrive\Desktop\protocol-zero\scripts\provision_grafana_demo_dashboard.ps1)
2. open `http://localhost:8000`
3. trigger a manual incident
4. show the generated post-mortem and code-fix artifact
