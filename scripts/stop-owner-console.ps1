param(
    [int]$Port = 8090,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $RepoRoot

$portPattern = "--port\s+$Port(\s|$)"
$processes = @(
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like "python*" -and
            $_.CommandLine -like "*src.owner_console_fastapi_launcher:app*" -and
            $_.CommandLine -match $portPattern
        }
)

if ($processes.Count -eq 0) {
    Write-Host "No Owner Console process found on port $Port."
    exit 0
}

foreach ($process in $processes) {
    Write-Host "Stopping Owner Console process $($process.ProcessId)..."
    if ($Force) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    } else {
        Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 1

$remaining = @(
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like "python*" -and
            $_.CommandLine -like "*src.owner_console_fastapi_launcher:app*" -and
            $_.CommandLine -match $portPattern
        }
)

if ($remaining.Count -gt 0) {
    Write-Host "Some Owner Console processes are still running:"
    $remaining | Select-Object ProcessId,Name,CommandLine | Format-List
    Write-Host "Run .\scripts\stop-owner-console.ps1 -Force if needed."
    exit 1
}

Write-Host "Owner Console stopped."
