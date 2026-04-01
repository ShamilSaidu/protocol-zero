param(
    [string]$GrafanaUrl = "http://localhost:3000",
    [string]$Username = "admin",
    [string]$Password = "admin123",
    [string]$Namespace = "default"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${Username}:${Password}"))
$headers = @{ Authorization = "Basic $auth" }

$datasources = Invoke-RestMethod -Uri "$GrafanaUrl/api/datasources" -Headers $headers -Method Get
$prometheus = $datasources | Where-Object { $_.type -eq "prometheus" -and $_.name -eq "Prometheus" } | Select-Object -First 1
$loki = $datasources | Where-Object { $_.type -eq "loki" -and $_.name -eq "Loki" } | Select-Object -First 1

if (-not $prometheus) {
    throw "Prometheus datasource not found in Grafana."
}

if (-not $loki) {
    throw "Loki datasource not found in Grafana."
}

$promDs = @{ type = "prometheus"; uid = $prometheus.uid }
$lokiDs = @{ type = "loki"; uid = $loki.uid }
$grafanaDs = @{ type = "datasource"; uid = "grafana" }

$targetsUpExpr = "sum(up{namespace=`"$Namespace`"})"
$totalRestartsExpr = "sum(kube_pod_container_status_restarts_total{namespace=`"$Namespace`"})"
$activePodsExpr = "count(kube_pod_info{namespace=`"$Namespace`"})"
$grafanaHealthExpr = 'sum(up{job="prometheus-grafana"})'
$cpuExpr = "sum by (pod) (rate(container_cpu_usage_seconds_total{namespace=`"$Namespace`",pod!=`"`"}[5m]))"
$memoryExpr = "sum by (pod) (container_memory_working_set_bytes{namespace=`"$Namespace`",pod!=`"`"}) / 1024 / 1024"
$restartByPodExpr = "sum by (pod) (kube_pod_container_status_restarts_total{namespace=`"$Namespace`"})"
$logsExpr = "{namespace=`"$Namespace`"}"

$dashboard = @{
    id = $null
    uid = "protocol-zero-demo"
    title = "Protocol Zero Demo"
    tags = @("protocol-zero", "demo", "observability")
    timezone = "browser"
    schemaVersion = 39
    version = 1
    editable = $true
    refresh = "5s"
    time = @{ from = "now-15m"; to = "now" }
    annotations = @{
        list = @(
            @{
                builtIn = 1
                datasource = $grafanaDs
                enable = $true
                hide = $true
                iconColor = "rgba(0, 211, 255, 1)"
                name = "Annotations & Alerts"
                type = "dashboard"
            }
        )
    }
    templating = @{ list = @() }
    panels = @(
        @{
            id = 1
            type = "stat"
            title = "Targets Up"
            datasource = $promDs
            gridPos = @{ h = 4; w = 6; x = 0; y = 0 }
            targets = @(
                @{ refId = "A"; expr = $targetsUpExpr; legendFormat = "" }
            )
            options = @{
                colorMode = "value"
                graphMode = "area"
                justifyMode = "auto"
                orientation = "auto"
                reduceOptions = @{ calcs = @("lastNotNull"); fields = ""; values = $false }
                textMode = "auto"
            }
            fieldConfig = @{ defaults = @{}; overrides = @() }
        }
        @{
            id = 2
            type = "stat"
            title = "Total Restarts"
            datasource = $promDs
            gridPos = @{ h = 4; w = 6; x = 6; y = 0 }
            targets = @(
                @{ refId = "A"; expr = $totalRestartsExpr; legendFormat = "" }
            )
            options = @{
                colorMode = "background"
                graphMode = "none"
                justifyMode = "center"
                orientation = "auto"
                reduceOptions = @{ calcs = @("lastNotNull"); fields = ""; values = $false }
                textMode = "value"
            }
            fieldConfig = @{ defaults = @{}; overrides = @() }
        }
        @{
            id = 3
            type = "stat"
            title = "Active Pods"
            datasource = $promDs
            gridPos = @{ h = 4; w = 6; x = 12; y = 0 }
            targets = @(
                @{ refId = "A"; expr = $activePodsExpr; legendFormat = "" }
            )
            options = @{
                colorMode = "value"
                graphMode = "none"
                justifyMode = "center"
                orientation = "auto"
                reduceOptions = @{ calcs = @("lastNotNull"); fields = ""; values = $false }
                textMode = "value"
            }
            fieldConfig = @{ defaults = @{}; overrides = @() }
        }
        @{
            id = 4
            type = "stat"
            title = "Grafana Health"
            datasource = $promDs
            gridPos = @{ h = 4; w = 6; x = 18; y = 0 }
            targets = @(
                @{ refId = "A"; expr = $grafanaHealthExpr; legendFormat = "" }
            )
            options = @{
                colorMode = "value"
                graphMode = "none"
                justifyMode = "center"
                orientation = "auto"
                reduceOptions = @{ calcs = @("lastNotNull"); fields = ""; values = $false }
                textMode = "value"
            }
            fieldConfig = @{ defaults = @{}; overrides = @() }
        }
        @{
            id = 5
            type = "timeseries"
            title = "CPU Usage by Pod"
            datasource = $promDs
            gridPos = @{ h = 9; w = 12; x = 0; y = 4 }
            targets = @(
                @{ refId = "A"; expr = $cpuExpr; legendFormat = "{{pod}}" }
            )
            options = @{ legend = @{ displayMode = "table"; placement = "bottom" }; tooltip = @{ mode = "multi"; sort = "desc" } }
            fieldConfig = @{ defaults = @{ unit = "cores" }; overrides = @() }
        }
        @{
            id = 6
            type = "timeseries"
            title = "Memory Working Set by Pod (MiB)"
            datasource = $promDs
            gridPos = @{ h = 9; w = 12; x = 12; y = 4 }
            targets = @(
                @{ refId = "A"; expr = $memoryExpr; legendFormat = "{{pod}}" }
            )
            options = @{ legend = @{ displayMode = "table"; placement = "bottom" }; tooltip = @{ mode = "multi"; sort = "desc" } }
            fieldConfig = @{ defaults = @{ unit = "short" }; overrides = @() }
        }
        @{
            id = 7
            type = "timeseries"
            title = "Restart Count by Pod"
            datasource = $promDs
            gridPos = @{ h = 8; w = 12; x = 0; y = 13 }
            targets = @(
                @{ refId = "A"; expr = $restartByPodExpr; legendFormat = "{{pod}}" }
            )
            options = @{ legend = @{ displayMode = "table"; placement = "bottom" }; tooltip = @{ mode = "multi"; sort = "desc" } }
            fieldConfig = @{ defaults = @{ unit = "short" }; overrides = @() }
        }
        @{
            id = 8
            type = "logs"
            title = "Live Cluster Logs"
            datasource = $lokiDs
            gridPos = @{ h = 8; w = 12; x = 12; y = 13 }
            targets = @(
                @{ refId = "A"; expr = $logsExpr; queryType = "range"; maxLines = 200 }
            )
            options = @{
                dedupStrategy = "none"
                enableLogDetails = $true
                prettifyLogMessage = $false
                showCommonLabels = $false
                showLabels = $true
                sortOrder = "Descending"
                wrapLogMessage = $true
            }
        }
    )
}

$payload = @{ dashboard = $dashboard; folderId = 0; overwrite = $true }
$body = $payload | ConvertTo-Json -Depth 30
$response = Invoke-RestMethod -Uri "$GrafanaUrl/api/dashboards/db" -Headers $headers -Method Post -ContentType "application/json" -Body $body
$response | ConvertTo-Json -Depth 10
