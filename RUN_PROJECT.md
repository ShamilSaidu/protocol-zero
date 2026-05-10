**activate env:**

cd C:\\Users\\shami\\OneDrive\\Desktop\\protocol-zero

.\\venv\\Scripts\\Activate.ps1



**deploy redis and post gres:**

docker start protocol-zero-db

docker start protocol-zero-redis



**check status :**

minikube status



**if not running :** 

minikube start --memory=6144 --cpus=3 --driver=docker



**verify :**

kubectl get pods



**Window 1:**

kubectl port-forward svc/frontend 8080:80



**Window 2:**

kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090



**Window 3:**

kubectl port-forward svc/prometheus-grafana 3000:80



**Window 4:**

kubectl port-forward svc/loki 3100:3100



**Window 5:**

cd C:\\Users\\shami\\OneDrive\\Desktop\\protocol-zero

.\\venv\\Scripts\\Activate.ps1

python main.py





**In a sixth PowerShell window, import the Grafana dashboard :**

cd C:\\Users\\shami\\OneDrive\\Desktop\\protocol-zero

.\\venv\\Scripts\\Activate.ps1

.\\scripts\\provision\_grafana\_demo\_dashboard.ps1





**Live faults :**
cd C:\\Users\\shami\\OneDrive\\Desktop\\protocol-zero

.\\venv\\Scripts\\Activate.ps1

.\\scripts\\chaos.ps1 -Action deployment-outage -Service cartservice



**Trigger detection :**

Invoke-RestMethod -Uri "http://localhost:8000/api/incidents/detect?auto\_process=true" -Method POST

Use `kill-pod` only for a quick pod churn demo. The current detector is much more reliable with `deployment-outage`, because it watches unavailable replicas rather than plain pod deletion.







