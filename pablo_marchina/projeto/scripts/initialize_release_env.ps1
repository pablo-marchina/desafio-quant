[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TemplatePath = Join-Path $ProjectRoot '.env.example'
$TargetPath = Join-Path $ProjectRoot '.env'

if (-not (Test-Path $TemplatePath)) {
    throw "Missing environment template: $TemplatePath"
}
if ((Test-Path $TargetPath) -and -not $Force) {
    throw ".env already exists. Use -Force only when you intend to replace it."
}

function New-RandomHex([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

$proxyKey = New-RandomHex 48
$databasePassword = New-RandomHex 32
$qdrantApiKey = New-RandomHex 32
$content = Get-Content -Raw -Path $TemplatePath
$content = $content.Replace(
    'replace-with-a-random-value-of-at-least-32-characters',
    $proxyKey
)
$content = $content.Replace(
    'replace-with-a-random-database-password',
    $databasePassword
)
$content = $content.Replace(
    'replace-with-a-random-qdrant-api-key',
    $qdrantApiKey
)

# Windows PowerShell 5.1 does not support `-Encoding utf8NoBOM`.
# Use the .NET API so the script behaves consistently in PowerShell 5.1 and 7+.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($TargetPath, $content, $utf8NoBom)

Write-Host "Created $TargetPath with cryptographically random local secrets."
Write-Host 'Open .env and add NVIDIA_API_KEY plus any optional governed collector keys.'
