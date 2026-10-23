param(
    [string]$ModelDir = "D:\OllamaModels",
    [string]$BaseUrl = "",
    [int]$TimeoutSec = 5,
    [int]$StartupWaitSec = 20,
    [switch]$NoStart,
    [switch]$Quiet,
    [string[]]$RequiredModels = @()
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

function Write-Ensure {
    param(
        [string]$Status,
        [string]$Message
    )
    if (-not $Quiet) {
        Write-Host ("[{0}] {1}" -f $Status, $Message)
    }
}

function Test-LocalOllamaUrl {
    param([string]$Url)
    try {
        $uri = [Uri]$Url
    } catch {
        return $false
    }
    return $uri.Scheme -in @("http", "https") -and
        $uri.Host -in @("127.0.0.1", "localhost", "::1") -and
        $uri.Port -eq 11434
}

function Get-OllamaTags {
    param(
        [string]$Url,
        [int]$Timeout
    )
    $tagsUrl = $Url.TrimEnd("/") + "/api/tags"
    return Invoke-RestMethod -Uri $tagsUrl -TimeoutSec $Timeout
}

function Get-ModelNames {
    param($Tags)
    if ($null -eq $Tags -or $null -eq $Tags.models) {
        return @()
    }
    return @($Tags.models | ForEach-Object { [string]$_.name } | Where-Object { $_ })
}

function Test-ModelPresent {
    param(
        [string[]]$Models,
        [string]$Expected
    )
    if ([string]::IsNullOrWhiteSpace($Expected)) {
        return $true
    }
    foreach ($model in $Models) {
        if ($model -eq $Expected) {
            return $true
        }
        if (-not $Expected.Contains(":") -and $model -eq "${Expected}:latest") {
            return $true
        }
    }
    return $false
}

function Get-MissingModels {
    param(
        [string[]]$Models,
        [string[]]$RequiredModels
    )
    $missing = @()
    foreach ($model in $RequiredModels) {
        if (-not (Test-ModelPresent $Models $model)) {
            $missing += $model
        }
    }
    return $missing
}

function Test-ConnectionRefusedException {
    param([System.Exception]$Exception)

    $current = $Exception
    while ($null -ne $current) {
        if (
            $current -is [System.Net.Sockets.SocketException] -and
            $current.SocketErrorCode -eq [System.Net.Sockets.SocketError]::ConnectionRefused
        ) {
            return $true
        }
        $current = $current.InnerException
    }
    return $false
}

if ($RequiredModels.Count -eq 0) {
    $python = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $configurationJson = & $python (Join-Path $PSScriptRoot "check_configuration.py") --json
    if ($LASTEXITCODE -ne 0) {
        Write-Ensure "ERR" "Configuration preflight failed; no service was contacted."
        Write-Host ($configurationJson -join "`n")
        exit 1
    }
    $configurationReport = ($configurationJson -join "`n") | ConvertFrom-Json
    $plans = @($configurationReport.ollama_local_plans)
    if ($plans.Count -eq 0) {
        Write-Ensure "OK" "Ollama ensure skipped: Ollama-backed RAG is disabled. No local Ollama dependency."
        exit 0
    }
    $plan = $plans[0]
    if ([string]::IsNullOrWhiteSpace($BaseUrl)) { $BaseUrl = $plan.base_url }
    $RequiredModels = @($plan.models)
}
$requiredModels = @($RequiredModels | Select-Object -Unique)
if ([string]::IsNullOrWhiteSpace($BaseUrl) -or $requiredModels.Count -eq 0 -or @($requiredModels | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
    Write-Ensure "ERR" "Ollama endpoint or required models are incomplete."
    exit 1
}

$isLocalUrl = Test-LocalOllamaUrl $BaseUrl
$shouldStart = (-not $NoStart) -and $isLocalUrl

Write-Ensure "INFO" "Checking Ollama at $BaseUrl"

try {
    $tags = Get-OllamaTags $BaseUrl $TimeoutSec
    $models = Get-ModelNames $tags
    $missing = Get-MissingModels $models $requiredModels
    if ($missing.Count -eq 0) {
        Write-Ensure "OK" ("Ollama is ready. Required RAG model(s): " + ($requiredModels -join ", "))
        exit 0
    }
    Write-Ensure "ERR" ("Ollama is reachable, but required model(s) are missing: " + ($missing -join ", "))
    Write-Ensure "ERR" "A healthy Ollama service will not be restarted for a missing model."
    exit 1
} catch {
    if (-not (Test-ConnectionRefusedException $_.Exception)) {
        Write-Ensure "ERR" "Ollama readiness is ambiguous; refusing to start or restart it: $($_.Exception.Message)"
        exit 1
    }
    Write-Ensure "WARN" "Ollama is explicitly offline (connection refused): $($_.Exception.Message)"
}

if (-not $shouldStart) {
    if ($NoStart) {
        Write-Ensure "ERR" "Ollama is not ready and -NoStart was specified."
    } else {
        Write-Ensure "ERR" "Ollama is not ready and $BaseUrl is not a supported local 11434 URL."
    }
    exit 1
}

$startScript = Join-Path $PSScriptRoot "start-ollama-vision.ps1"
if (-not (Test-Path -LiteralPath $startScript)) {
    Write-Ensure "ERR" "Missing start script: $startScript"
    exit 1
}

Write-Ensure "INFO" "Starting Ollama with model directory: $ModelDir"
& $startScript -ModelDir $ModelDir -KeepExisting
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$deadline = (Get-Date).AddSeconds($StartupWaitSec)
do {
    Start-Sleep -Seconds 1
    try {
        $tags = Get-OllamaTags $BaseUrl $TimeoutSec
        $models = Get-ModelNames $tags
        $missing = Get-MissingModels $models $requiredModels
        if ($missing.Count -eq 0) {
            Write-Ensure "OK" ("Ollama is ready after start. Required RAG model(s): " + ($requiredModels -join ", "))
            exit 0
        }
        Write-Ensure "WARN" ("Ollama started, but required model(s) are still missing: " + ($missing -join ", "))
        exit 1
    } catch {
        if ((Get-Date) -ge $deadline) {
            Write-Ensure "ERR" "Ollama did not become ready before timeout: $($_.Exception.Message)"
            exit 1
        }
    }
} while ($true)
