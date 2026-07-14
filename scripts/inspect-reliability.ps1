param(
    [ValidateRange(1, 720)]
    [int]$Hours = 24,
    [switch]$WriteReport
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "[configuration/python_environment_missing] .venv Python was not found; inspection did not run."
    exit 2
}

if ($WriteReport) {
    & $python '.\scripts\reliability_inspection.py' '--hours' $Hours '--write-report'
} else {
    & $python '.\scripts\reliability_inspection.py' '--hours' $Hours
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "[data/inspection_execution_failed] Inspection failed; run .\scripts\diagnose.ps1 for base diagnostics."
    exit $LASTEXITCODE
}

exit 0
