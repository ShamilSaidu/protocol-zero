$requiredDirs = @(
    "agents",
    "orchestrator",
    "remediation",
    "monitoring",
    "post_mortem",
    "database",
    "integrations",
    "tests"
)

$requiredFiles = @(
    "requirements.txt",
    ".env",
    ".gitignore",
    ".env.example",
    "scripts\test_groq.py"
)

Write-Host "=== Phase 0 Verification ===" -ForegroundColor Cyan

foreach ($dir in $requiredDirs) {
    if (Test-Path $dir) {
        Write-Host "OK  $dir/" -ForegroundColor Green
    } else {
        Write-Host "MISS $dir/" -ForegroundColor Red
    }
}

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "OK  $file" -ForegroundColor Green
    } else {
        Write-Host "MISS $file" -ForegroundColor Red
    }
}

if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "OK  venv\\Scripts\\Activate.ps1" -ForegroundColor Green
} else {
    Write-Host "MISS venv\\Scripts\\Activate.ps1" -ForegroundColor Yellow
}
