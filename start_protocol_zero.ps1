Write-Host "Starting Protocol Zero helper workflow..." -ForegroundColor Cyan

try { docker start protocol-zero-db | Out-Null } catch {}
try { docker start protocol-zero-redis | Out-Null } catch {}

Write-Host "Opening port-forwards in new windows..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'kubectl port-forward svc/frontend 8080:80'
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090'
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'kubectl port-forward svc/prometheus-grafana 3000:80'
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'kubectl port-forward svc/loki 3100:3100'

Write-Host "Launching Protocol Zero API..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd "' + (Get-Location).Path + '"; .\venv\Scripts\Activate.ps1; python main.py'

Write-Host "Done. Dashboard should be available at http://localhost:8000" -ForegroundColor Green
