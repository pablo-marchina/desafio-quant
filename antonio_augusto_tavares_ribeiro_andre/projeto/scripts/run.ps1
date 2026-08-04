# run.ps1 — sobe o TAPI inteiro com UM comando (F0.2 / F7.7).
#
# Faz, em ordem: checa o Docker -> sobe a stack (build) -> espera o Postgres ->
# cria o schema (alembic) -> popula a coorte real (best-effort) -> abre a UI.
#
# Uso (PowerShell, na raiz do repo):
#   .\scripts\run.ps1            # sobe tudo (sem GPU), migra, popula, abre http://localhost:3000
#   .\scripts\run.ps1 -Gpu       # inclui o NIM self-hosted (requer entitlement NGC + Container Toolkit)
#   .\scripts\run.ps1 -Down      # derruba a stack
#   .\scripts\run.ps1 -NoSeed    # sobe sem popular (UI vazia)
#   .\scripts\run.ps1 -Demo      # config a prova de rate limit do NIM p/ o video: aplica .env.demo
#                                # POR CIMA do .env (cache ON, so extractor no LLM, render local,
#                                # HITL ON). NAO altera o .env padrao (config completa p/ a arquitetura).
#
# Pre-requisitos: Docker Desktop ABERTO ("Engine running") + .env preenchido + .venv criado.
#
# Obs. PowerShell 5.1: NAO usamos `*> $null`/`2>$null` em comando nativo (docker escreve WARNINGs
# no stderr -> viram NativeCommandError fatal). As checagens silenciosas passam por `cmd /c`, que
# isola o stderr do PowerShell; os comandos "barulhentos" rodam direto (saida visivel, sem Stop).

param(
    [switch]$Down,
    [switch]$Gpu,
    [switch]$NoSeed,
    [switch]$Demo
)

$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo

function Fail([string]$msg) { Write-Host "ERRO: $msg" -ForegroundColor Red; exit 1 }
function Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
# Exit code de comando nativo SEM poluir o console e SEM o stderr virar erro fatal (cmd isola).
function Quiet([string]$cmd) { cmd /c "$cmd >nul 2>nul"; return $LASTEXITCODE }

# 0) Docker daemon de pe? (o erro 'dockerDesktopLinuxEngine' = Desktop fechado).
if ((Quiet "docker info") -ne 0) {
    Fail "Docker nao respondeu. Abra o Docker Desktop, espere 'Engine running' e rode de novo."
}

if ($Down) {
    Step "Derrubando a stack (docker compose down)..."
    docker compose down
    exit $LASTEXITCODE
}

if (-not (Test-Path "$repo\.env")) {
    Fail ".env nao encontrado. Copie .env.example -> .env e preencha as chaves."
}
$python = "$repo\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { Fail ".venv nao encontrado em .venv\Scripts\python.exe." }

# 1) Sobe a stack. A 1a vez COMPILA as imagens (api/worker + frontend) -> pode levar 10-20 min.
# -Demo: sobrepoe .env.demo ao .env (so api/worker) via override do compose, sem tocar no .env.
$demoFiles = @()
if ($Demo) {
    if (-not (Test-Path "$repo\.env.demo")) { Fail ".env.demo nao encontrado (necessario p/ -Demo)." }
    $demoFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.demo.yml")
    Step "Modo DEMO: .env + .env.demo (cache ON, so extractor no LLM, render local, HITL ON)."
}
Step "Subindo a stack (1a vez compila as imagens; pode levar 10-20 min)..."
if ($Gpu) { docker compose @demoFiles --profile gpu up -d --build }
else { docker compose @demoFiles up -d --build }
if ($LASTEXITCODE -ne 0) { Fail "docker compose up falhou (veja o log acima)." }

# 2) Espera o Postgres aceitar conexao (ate ~60s).
Step "Esperando o Postgres ficar pronto..."
$ready = $false
foreach ($i in 1..30) {
    if ((Quiet "docker compose exec -T postgres pg_isready -U tapi") -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Fail "Postgres nao ficou pronto a tempo (veja 'docker compose logs postgres')." }

# 3) Cria o schema no Postgres (Alembic do venv -> localhost:5432, que o compose expoe).
Step "Aplicando migrations (alembic upgrade head)..."
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail "alembic upgrade head falhou." }

# 4) Popula a coorte real (best-effort: se falhar, a UI sobe vazia, sem quebrar o run).
if (-not $NoSeed) {
    Step "Populando a coorte real (data/cohort.db -> Postgres)..."
    & $python "$repo\scripts\seed_postgres.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "AVISO: seed falhou; a UI sobe vazia. Rode uma consulta na UI ou popule depois." -ForegroundColor Yellow
    }
}

# 5) Pronto.
Write-Host ""
Write-Host "TAPI no ar:" -ForegroundColor Green
Write-Host "  Frontend : http://localhost:3000"
Write-Host "  API/docs : http://localhost:8080/docs"
Write-Host "  Langfuse : http://localhost:3001  (traces dos agentes)"
if ($Gpu) { Write-Host "  NIM GPU  : http://localhost:8000/v1" }
Start-Process "http://localhost:3000"
Write-Host ""
Write-Host "Logs ao vivo : docker compose logs -f api worker frontend" -ForegroundColor DarkGray
Write-Host "Derrubar     : .\scripts\run.ps1 -Down" -ForegroundColor DarkGray
