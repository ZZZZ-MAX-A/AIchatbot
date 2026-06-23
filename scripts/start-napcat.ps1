$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$napcatDir = Join-Path $projectRoot "tools\NapCatQQ\bootmain"
$quickBat = Join-Path $napcatDir "napcat.quick.bat"
$normalBat = Join-Path $napcatDir "napcat.bat"
$installer = Join-Path $projectRoot "tools\NapCatQQ\NapCatInstaller.exe"

Write-Host "If this is your first NapCatQQ launch, run:"
Write-Host ".\scripts\install-napcat.ps1"
Write-Host ""

if (Test-Path $quickBat) {
    Start-Process -FilePath $quickBat -WorkingDirectory $napcatDir
    exit 0
}

if (Test-Path $normalBat) {
    Start-Process -FilePath $normalBat -WorkingDirectory $napcatDir
    exit 0
}

Write-Host "NapCatQQ startup script was not found."
Write-Host "Expected one of:"
Write-Host $quickBat
Write-Host $normalBat
exit 1
