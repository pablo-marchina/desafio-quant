param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$DatasetPath = "docs/recommendations/datasets/golden_startups_br20.json",
    [int]$BatchSize = 5,
    [int]$WaitSeconds = 2,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $DatasetPath)) {
    throw "Dataset not found: $DatasetPath"
}

$dataset = Get-Content -Raw -LiteralPath $DatasetPath | ConvertFrom-Json
$items = @($dataset.items)

Write-Host "Dataset: $($dataset.dataset_id) v$($dataset.version)"
Write-Host "Items: $($items.Count)"
Write-Host "Backend: $ApiBaseUrl"
Write-Host ""

$results = New-Object System.Collections.Generic.List[object]
$index = 0

foreach ($item in $items) {
    $index += 1
    $body = @{
        url = $item.website_url
        source_type = "startup_evidence"
    } | ConvertTo-Json -Depth 4

    Write-Host ("[{0}/{1}] {2} -> {3}" -f $index, $items.Count, $item.name, $item.website_url)

    if ($DryRun) {
        $results.Add([pscustomobject]@{
            dataset_item_id = $item.id
            name = $item.name
            website_url = $item.website_url
            expected_ai_maturity = $item.expected_ai_maturity
            submitted = $false
            job_id = $null
            status = "dry_run"
            error = $null
        })
    }
    else {
        try {
            $response = Invoke-RestMethod `
                -Method Post `
                -Uri "$ApiBaseUrl/url-ingestion/jobs" `
                -ContentType "application/json" `
                -Body $body

            $results.Add([pscustomobject]@{
                dataset_item_id = $item.id
                name = $item.name
                website_url = $item.website_url
                expected_ai_maturity = $item.expected_ai_maturity
                submitted = $true
                job_id = $response.id
                status = $response.status
                error = $null
            })
        }
        catch {
            $results.Add([pscustomobject]@{
                dataset_item_id = $item.id
                name = $item.name
                website_url = $item.website_url
                expected_ai_maturity = $item.expected_ai_maturity
                submitted = $false
                job_id = $null
                status = "failed_to_submit"
                error = $_.Exception.Message
            })
            Write-Warning ("Failed to submit {0}: {1}" -f $item.name, $_.Exception.Message)
        }
    }

    if (($index % $BatchSize) -eq 0 -and $index -lt $items.Count) {
        Write-Host "Waiting $WaitSeconds seconds before next batch..."
        Start-Sleep -Seconds $WaitSeconds
    }
}

$runDir = "docs/recommendations/datasets/runs"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputPath = Join-Path $runDir "golden_startups_br20_jobs_$timestamp.json"

$run = [pscustomobject]@{
    dataset_id = $dataset.dataset_id
    dataset_version = $dataset.version
    submitted_at = (Get-Date).ToString("o")
    api_base_url = $ApiBaseUrl
    dry_run = [bool]$DryRun
    results = $results
}

$run | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outputPath -Encoding UTF8

Write-Host ""
Write-Host "Saved run file: $outputPath"
$results | Format-Table name, expected_ai_maturity, submitted, job_id, status -AutoSize
