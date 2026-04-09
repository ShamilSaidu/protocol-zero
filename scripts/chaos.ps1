param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("list-services","kill-pod","restart-deployment","scale","deployment-outage")]
    [string]$Action,
    [string]$Service = "cartservice",
    [int]$Replicas = 2,
    [string]$Namespace = "default"
)

switch ($Action) {
    "list-services" {
        kubectl get svc -n $Namespace
    }
    "kill-pod" {
        $pod = kubectl get pods -n $Namespace -l app=$Service -o jsonpath='{.items[0].metadata.name}'
        if (-not $pod) { throw "No pod found for service '$Service'" }
        kubectl delete pod $pod -n $Namespace
    }
    "restart-deployment" {
        kubectl rollout restart deployment/$Service -n $Namespace
    }
    "scale" {
        kubectl scale deployment/$Service -n $Namespace --replicas=$Replicas
    }
    "deployment-outage" {
        kubectl scale deployment/$Service -n $Namespace --replicas=0
    }
}
