param(
    [string]$ModelDir = "D:\OllamaModels",
    [switch]$KeepExisting,
    [switch]$PersistUserEnv
)

$ErrorActionPreference = "Stop"

$resolvedModelDir = (Resolve-Path -LiteralPath $ModelDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $resolvedModelDir "blobs"))) {
    throw "Ollama model directory must contain a blobs folder: $resolvedModelDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedModelDir "manifests"))) {
    throw "Ollama model directory must contain a manifests folder: $resolvedModelDir"
}

if ($PersistUserEnv) {
    [Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $resolvedModelDir, "User")
}

if (-not $KeepExisting) {
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -in @("ollama", "ollama app") } |
        Stop-Process -Force
    Start-Sleep -Seconds 2
}

$ollamaCommand = Get-Command ollama -ErrorAction Stop
$env:OLLAMA_MODELS = $resolvedModelDir

Start-Process `
    -FilePath $ollamaCommand.Source `
    -ArgumentList "serve" `
    -WorkingDirectory (Split-Path -Parent $ollamaCommand.Source) `
    -WindowStyle Hidden

Start-Sleep -Seconds 3

Write-Host "OLLAMA_MODELS=$env:OLLAMA_MODELS"
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10 |
        ConvertTo-Json -Depth 6
} catch {
    Write-Host "Ollama started, but /api/tags is not ready yet: $($_.Exception.Message)"
}
