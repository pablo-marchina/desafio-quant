# NVIDIA Startup AI Radar - Local Development Script
# This script sets up the database and shows how to run the project.

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  NVIDIA Startup AI Radar - Toph" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

$VenvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$AlembicDir = Join-Path $PSScriptRoot "ai-agent-system\src\radar\database"
$AlembicIni = Join-Path $AlembicDir "alembic.ini"

if (-not (Test-Path $VenvPython)) {
    Write-Warning "Virtual environment not found at: $VenvPython"
    Write-Warning "Create it with: python -m venv venv"
    exit 1
}

# Step 1: Database migrations
Write-Host "[1/1] Running database migrations..." -ForegroundColor Yellow
Push-Location (Join-Path $PSScriptRoot "ai-agent-system")
try {
    $env:PYTHONPATH = "$(Get-Location)\src"
    & $VenvPython -c @"
from pathlib import Path
from alembic.config import Config
from alembic import command
ini = Path(r'$AlembicIni').resolve()
cfg = Config(str(ini))
cfg.set_main_option('script_location', str(ini.parent / 'alembic'))
command.upgrade(cfg, 'head')
print('Migrations applied successfully.')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Migration failed"
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "To run the project, open TWO terminals:" -ForegroundColor White
Write-Host ""
Write-Host "  Terminal 1 - Backend (FastAPI):" -ForegroundColor Cyan
Write-Host "    cd $PSScriptRoot\ai-agent-system"
Write-Host "    $VenvPython -m uvicorn radar.api.app:app --reload --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "  Terminal 2 - Frontend (Vite):" -ForegroundColor Cyan
Write-Host "    cd $PSScriptRoot\frontend"
Write-Host "    npm run dev"
Write-Host ""
Write-Host "  Open: http://localhost:5173" -ForegroundColor Green
Write-Host ""
