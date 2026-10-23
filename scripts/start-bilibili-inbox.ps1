param([switch]$Background)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = "utf-8"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$entry = Join-Path $RepoRoot "scripts\bilibili_inbox.py"
Set-Location -LiteralPath $RepoRoot
if (-not (Test-Path -LiteralPath $python)) { throw "Project Python is missing." }
$statusLines = @(& $python $entry status)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$current = $statusLines[0] | ConvertFrom-Json
if ($current.running) {
    Write-Host "Bilibili private replies are already running."
    $statusLines | ForEach-Object { Write-Host $_ }
    exit 0
}
& $python $entry init
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Background) {
    & $python $entry start
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python $entry status
} else {
    & $python -u $entry run
    exit $LASTEXITCODE
}
