[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:3000/api",
    [int]$PipelineLimit = 1,
    [int]$RequestTimeoutSeconds = 1800,
    [switch]$SkipRebuild,
    [switch]$KeepReportOnFailure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$reportDirectory = Join-Path $repoRoot "final_case_evidence"
$reportPath = Join-Path $reportDirectory "local_runtime_output_validation.json"
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null

$checks = [ordered]@{}
$failures = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
$startedAt = [DateTimeOffset]::UtcNow

function Add-Check {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [bool]$Passed,
        [Parameter(Mandatory)] [string]$Detail
    )
    $checks[$Name] = [ordered]@{
        passed = $Passed
        detail = $Detail
    }
    if (-not $Passed) {
        $failures.Add("${Name}: ${Detail}")
    }
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory)] [string]$Description,
        [Parameter(Mandatory)] [scriptblock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "${Description} failed with exit code $LASTEXITCODE."
    }
}

function Invoke-JsonRequest {
    param(
        [Parameter(Mandatory)] [ValidateSet("GET", "POST")] [string]$Method,
        [Parameter(Mandatory)] [string]$Uri
    )
    return Invoke-RestMethod `
        -Method $Method `
        -Uri $Uri `
        -TimeoutSec $RequestTimeoutSeconds `
        -Headers @{ Accept = "application/json" }
}

function Convert-ComposePsOutput {
    param([Parameter(Mandatory)] [object[]]$RawLines)

    $joined = ($RawLines | ForEach-Object { [string]$_ }) -join "`n"
    if ([string]::IsNullOrWhiteSpace($joined)) {
        return @()
    }

    try {
        $parsed = $joined | ConvertFrom-Json
        return @($parsed)
    }
    catch {
        $items = @()
        foreach ($line in $RawLines) {
            $value = [string]$line
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $items += $value | ConvertFrom-Json
            }
        }
        return @($items)
    }
}

function Get-ServiceRecord {
    param(
        [Parameter(Mandatory)] [object[]]$Services,
        [Parameter(Mandatory)] [string]$ServiceName
    )
    return @($Services | Where-Object { [string]$_.Service -eq $ServiceName }) | Select-Object -First 1
}

function Assert-PersistentService {
    param(
        [Parameter(Mandatory)] [object[]]$Services,
        [Parameter(Mandatory)] [string]$ServiceName,
        [switch]$RequireHealthy
    )

    $record = Get-ServiceRecord -Services $Services -ServiceName $ServiceName
    if ($null -eq $record) {
        Add-Check -Name "service.${ServiceName}" -Passed $false -Detail "Service is missing from docker compose ps."
        return
    }

    $state = ([string]$record.State).ToLowerInvariant()
    $health = ([string]$record.Health).ToLowerInvariant()
    $running = $state -eq "running"
    $healthOk = (-not $RequireHealthy) -or $health -eq "healthy"
    Add-Check `
        -Name "service.${ServiceName}" `
        -Passed ($running -and $healthOk) `
        -Detail "state=$state health=$health"
}

function Assert-OneShotService {
    param(
        [Parameter(Mandatory)] [object[]]$Services,
        [Parameter(Mandatory)] [string]$ServiceName
    )

    $record = Get-ServiceRecord -Services $Services -ServiceName $ServiceName
    if ($null -eq $record) {
        Add-Check -Name "service.${ServiceName}" -Passed $false -Detail "One-shot service is missing."
        return
    }

    $state = ([string]$record.State).ToLowerInvariant()
    $exitCode = 0
    if ($null -ne $record.ExitCode -and [string]$record.ExitCode -ne "") {
        $exitCode = [int]$record.ExitCode
    }
    Add-Check `
        -Name "service.${ServiceName}" `
        -Passed ($state -eq "exited" -and $exitCode -eq 0) `
        -Detail "state=$state exit_code=$exitCode"
}

function Test-ForbiddenRuntimeError {
    param([string]$Text)
    $patterns = @(
        "NameError: name 'max_sources' is not defined",
        "NameError: name 'failures' is not defined",
        "NameError: name 'datetime' is not defined",
        "Multiple head revisions",
        "Revision h8i9j0k1l2m3 is present more than once"
    )
    foreach ($pattern in $patterns) {
        if ($Text -like "*${pattern}*") {
            return $pattern
        }
    }
    return $null
}

try {
    if (-not $SkipRebuild) {
        Invoke-NativeChecked -Description "Backend/frontend build" -Command {
            docker compose build --progress=plain api frontend
        }
        Invoke-NativeChecked -Description "Service recreation" -Command {
            docker compose up -d --force-recreate api workflow-worker frontend
        }
    }

    $deadline = [DateTimeOffset]::UtcNow.AddMinutes(5)
    $services = @()
    do {
        $rawPs = @(docker compose ps -a --format json)
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose ps failed with exit code $LASTEXITCODE."
        }
        $services = Convert-ComposePsOutput -RawLines $rawPs
        $api = Get-ServiceRecord -Services $services -ServiceName "api"
        $frontend = Get-ServiceRecord -Services $services -ServiceName "frontend"
        $worker = Get-ServiceRecord -Services $services -ServiceName "workflow-worker"
        $ready = `
            $null -ne $api -and ([string]$api.Health).ToLowerInvariant() -eq "healthy" -and `
            $null -ne $frontend -and ([string]$frontend.Health).ToLowerInvariant() -eq "healthy" -and `
            $null -ne $worker -and ([string]$worker.Health).ToLowerInvariant() -eq "healthy"
        if (-not $ready) {
            Start-Sleep -Seconds 5
        }
    } while (-not $ready -and [DateTimeOffset]::UtcNow -lt $deadline)

    Assert-PersistentService -Services $services -ServiceName "postgres" -RequireHealthy
    Assert-PersistentService -Services $services -ServiceName "qdrant"
    Assert-PersistentService -Services $services -ServiceName "triton-reranker" -RequireHealthy
    Assert-PersistentService -Services $services -ServiceName "api" -RequireHealthy
    Assert-PersistentService -Services $services -ServiceName "workflow-worker" -RequireHealthy
    Assert-PersistentService -Services $services -ServiceName "frontend" -RequireHealthy
    Assert-OneShotService -Services $services -ServiceName "init-volumes"
    Assert-OneShotService -Services $services -ServiceName "migrate"
    Assert-OneShotService -Services $services -ServiceName "rag-bootstrap"

    $live = Invoke-JsonRequest -Method GET -Uri "${ApiBaseUrl}/health/live"
    Add-Check -Name "api.health.live" -Passed ($null -ne $live) -Detail "HTTP request completed."

    $readyResponse = Invoke-JsonRequest -Method GET -Uri "${ApiBaseUrl}/health/ready"
    Add-Check -Name "api.health.ready" -Passed ($null -ne $readyResponse) -Detail "HTTP request completed."

    $qualityReport = Invoke-JsonRequest -Method GET -Uri "${ApiBaseUrl}/product/quality-report"
    Add-Check `
        -Name "api.product.quality_report" `
        -Passed ($null -ne $qualityReport -and $null -ne $qualityReport.last_updated) `
        -Detail "Endpoint returned last_updated without datetime NameError."

    $readiness = Invoke-JsonRequest -Method GET -Uri "${ApiBaseUrl}/product/readiness"
    $readinessJson = $readiness | ConvertTo-Json -Depth 30 -Compress
    $readinessHasFailure = $readinessJson -match '"status":"failed"|"status":"blocked"'
    Add-Check `
        -Name "product.readiness" `
        -Passed (-not $readinessHasFailure) `
        -Detail $(if ($readinessHasFailure) { "Readiness contains failed/blocked checks." } else { "No failed/blocked readiness status." })

    $populateUri = "${ApiBaseUrl}/radar/dashboard/populate?limit=100&source_limit=0&pipeline_limit=${PipelineLimit}&run_pipeline=true&force_rerun=true"
    $populate = Invoke-JsonRequest -Method POST -Uri $populateUri
    $pipelineResults = @($populate.pipeline_results)
    Add-Check `
        -Name "pipeline.result_count" `
        -Passed ($pipelineResults.Count -ge 1) `
        -Detail "pipeline_results=$($pipelineResults.Count)"

    $acceptedStatuses = @("completed", "degraded", "awaiting_review")
    $analysisSummaries = @()
    foreach ($result in $pipelineResults) {
        $status = ([string]$result.status).ToLowerInvariant()
        $errorText = [string]$result.error
        $forbidden = Test-ForbiddenRuntimeError -Text $errorText
        $statusAccepted = $acceptedStatuses -contains $status
        $runtimeClean = [string]::IsNullOrWhiteSpace($errorText) -and $null -eq $forbidden
        if ($status -eq "degraded") {
            $reason = [string]$result.degraded_reason
            $runtimeClean = $null -eq (Test-ForbiddenRuntimeError -Text $reason)
            if ([string]::IsNullOrWhiteSpace($reason)) {
                $runtimeClean = $false
            }
        }
        Add-Check `
            -Name "pipeline.$([string]$result.startup_id)" `
            -Passed ($statusAccepted -and $runtimeClean) `
            -Detail "status=$status error=$errorText degraded_reason=$([string]$result.degraded_reason)"

        $runId = [string]$result.analysis_run_id
        if ([string]::IsNullOrWhiteSpace($runId)) {
            $failures.Add("Pipeline result for $([string]$result.startup_id) has no analysis_run_id.")
            continue
        }

        $run = Invoke-JsonRequest -Method GET -Uri "${ApiBaseUrl}/analysis-runs/${runId}"
        $runStatus = ([string]$run.status).ToLowerInvariant()
        $runError = [string]$run.error_message
        $runForbidden = Test-ForbiddenRuntimeError -Text $runError
        Add-Check `
            -Name "analysis_run.${runId}" `
            -Passed (($acceptedStatuses -contains $runStatus) -and $null -eq $runForbidden -and $runStatus -ne "failed") `
            -Detail "status=$runStatus error_message=$runError"

        $analysisSummaries += [ordered]@{
            startup_id = [string]$result.startup_id
            analysis_run_id = $runId
            workflow_id = [string]$result.workflow_id
            status = $runStatus
            degraded_reason = [string]$run.degraded_reason
            error_message = $runError
        }
    }

    $dashboard = Invoke-JsonRequest -Method GET -Uri "${ApiBaseUrl}/radar/dashboard?limit=100"
    $dashboardItems = @($dashboard.items)
    Add-Check `
        -Name "dashboard.persisted_output" `
        -Passed ($dashboardItems.Count -ge 1) `
        -Detail "dashboard_items=$($dashboardItems.Count) analyzed_total=$([string]$dashboard.analyzed_total)"

    $runtimeLogs = @(docker compose logs --no-color --since=15m api workflow-worker) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose logs failed with exit code $LASTEXITCODE."
    }
    $forbiddenLogError = Test-ForbiddenRuntimeError -Text $runtimeLogs
    Add-Check `
        -Name "runtime.forbidden_regressions" `
        -Passed ($null -eq $forbiddenLogError) `
        -Detail $(if ($null -eq $forbiddenLogError) { "No known regression signature in recent logs." } else { "Found: $forbiddenLogError" })

    $overallPassed = $failures.Count -eq 0
    $report = [ordered]@{
        status = $(if ($overallPassed) { "passed" } else { "failed" })
        started_at = $startedAt.ToString("o")
        completed_at = [DateTimeOffset]::UtcNow.ToString("o")
        api_base_url = $ApiBaseUrl
        pipeline_limit = $PipelineLimit
        checks = $checks
        failures = @($failures)
        warnings = @($warnings)
        analysis_runs = $analysisSummaries
    }
    $report | ConvertTo-Json -Depth 30 | Set-Content -Path $reportPath -Encoding UTF8

    if (-not $overallPassed) {
        throw "Runtime output validation failed. See $reportPath."
    }

    Write-Host "Runtime output validation PASSED."
    Write-Host "Report: $reportPath"
}
catch {
    if ($true) {
        $failureReport = [ordered]@{
            status = "failed"
            started_at = $startedAt.ToString("o")
            completed_at = [DateTimeOffset]::UtcNow.ToString("o")
            api_base_url = $ApiBaseUrl
            checks = $checks
            failures = @($failures) + @($_.Exception.Message)
            warnings = @($warnings)
        }
        $failureReport | ConvertTo-Json -Depth 30 | Set-Content -Path $reportPath -Encoding UTF8
    }
    Write-Error $_
    exit 1
}


