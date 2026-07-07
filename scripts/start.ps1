param(
    [switch]$SkipOllamaEnsure
)

$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Virtual environment not found. Run .\scripts\setup.ps1 first."
    exit 1
}

if (-not $SkipOllamaEnsure -and $env:SKIP_OLLAMA_ENSURE -notin @("1", "true", "yes", "on")) {
    & .\scripts\ensure-ollama.ps1
}

& .\.venv\Scripts\python.exe .\bot.py
