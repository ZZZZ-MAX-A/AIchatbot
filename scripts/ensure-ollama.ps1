param(
    [string]$ModelDir = "D:\OllamaModels",
    [string]$BaseUrl = "",
    [int]$TimeoutSec = 5,
    [int]$StartupWaitSec = 20,
    [switch]$NoStart,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$dotEnvPath = Join-Path $repoRoot ".env"

function Write-Ensure {
    param(
        [string]$Status,
        [string]$Message
    )
    if (-not $Quiet) {
        Write-Host ("[{0}] {1}" -f $Status, $Message)
    }
}

function Normalize-DotEnvValue {
    param([string]$Value)
    $trimmed = $Value.Trim()
    if (
        ($trimmed.StartsWith('"') -and $trimmed.EndsWith('"')) -or
        ($trimmed.StartsWith("'") -and $trimmed.EndsWith("'"))
    ) {
        return $trimmed.Substring(1, $trimmed.Length - 2)
    }
    return $trimmed
}

function Read-DotEnv {
    param([string]$Path)
    $result = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $result
    }
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line.Split("=", 2)
        $result[$key.Trim()] = Normalize-DotEnvValue $value
    }
    return $result
}

$dotEnv = Read-DotEnv $dotEnvPath

function Get-ConfigValue {
    param(
        [string]$Name,
        [string]$Default = ""
    )
    $processValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue
    }
    if ($dotEnv.ContainsKey($Name) -and -not [string]::IsNullOrWhiteSpace($dotEnv[$Name])) {
        return $dotEnv[$Name]
    }
    return $Default
}

function Get-BoolConfig {
    param(
        [string]$Name,
        [bool]$Default
    )
    $value = Get-ConfigValue $Name ""
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    $normalized = $value.Trim().ToLowerInvariant()
    if ($normalized -in @("1", "true", "yes", "on")) {
        return $true
    }
    if ($normalized -in @("0", "false", "no", "off")) {
        return $false
    }
    return $Default
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

$enableVision = Get-BoolConfig "ENABLE_VISION" $true
$enableMemoryRag = Get-BoolConfig "ENABLE_MEMORY_RAG" $false
$enableProjectDocRag = Get-BoolConfig "ENABLE_PROJECT_DOC_RAG" $false
$embeddingProvider = (Get-ConfigValue "MEMORY_RAG_EMBEDDING_PROVIDER" "ollama").Trim().ToLowerInvariant()

$needsOllama = $enableVision -or (($enableMemoryRag -or $enableProjectDocRag) -and $embeddingProvider -eq "ollama")
if (-not $needsOllama) {
    Write-Ensure "OK" "Ollama ensure skipped: vision and Ollama-backed RAG are disabled."
    exit 0
}

$visionBaseUrl = Get-ConfigValue "VISION_OLLAMA_BASE_URL" "http://127.0.0.1:11434"
$embeddingBaseUrl = Get-ConfigValue "MEMORY_RAG_EMBEDDING_BASE_URL" "http://127.0.0.1:11434"
if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = if ($enableVision) { $visionBaseUrl } else { $embeddingBaseUrl }
}

$requiredModels = @()
if ($enableVision) {
    $requiredModels += Get-ConfigValue "VISION_MODEL" "qwen2.5vl:3b"
}
if (($enableMemoryRag -or $enableProjectDocRag) -and $embeddingProvider -eq "ollama") {
    $requiredModels += Get-ConfigValue "MEMORY_RAG_EMBEDDING_MODEL" "bge-m3"
}
$requiredModels = @($requiredModels | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

$isLocalUrl = Test-LocalOllamaUrl $BaseUrl
$shouldStart = (-not $NoStart) -and $isLocalUrl

Write-Ensure "INFO" "Checking Ollama at $BaseUrl"

$needsRestart = $false
try {
    $tags = Get-OllamaTags $BaseUrl $TimeoutSec
    $models = Get-ModelNames $tags
    $missing = Get-MissingModels $models $requiredModels
    if ($missing.Count -eq 0) {
        Write-Ensure "OK" ("Ollama is ready. Models: " + ($models -join ", "))
        exit 0
    }
    Write-Ensure "WARN" ("Ollama is reachable, but required model(s) are missing: " + ($missing -join ", "))
    $needsRestart = $true
} catch {
    Write-Ensure "WARN" "Ollama API is not reachable: $($_.Exception.Message)"
    $needsRestart = $true
}

if (-not $needsRestart) {
    exit 0
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
& $startScript -ModelDir $ModelDir

$deadline = (Get-Date).AddSeconds($StartupWaitSec)
do {
    Start-Sleep -Seconds 1
    try {
        $tags = Get-OllamaTags $BaseUrl $TimeoutSec
        $models = Get-ModelNames $tags
        $missing = Get-MissingModels $models $requiredModels
        if ($missing.Count -eq 0) {
            Write-Ensure "OK" ("Ollama is ready after start. Models: " + ($models -join ", "))
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
