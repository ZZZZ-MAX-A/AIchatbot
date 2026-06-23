$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $projectRoot "tools\NapCatQQ\NapCatInstaller.exe"

if (-not (Test-Path $installer)) {
    Write-Host "NapCatInstaller.exe was not found."
    Write-Host "Expected: $installer"
    exit 1
}

Start-Process -FilePath $installer -WorkingDirectory (Split-Path -Parent $installer)
