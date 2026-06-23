param(
    [string]$QQNumber = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$napcatDir = Join-Path $projectRoot "tools\NapCatShell"
$launcher = Join-Path $napcatDir "launcher-user.bat"
$envFile = Join-Path $projectRoot ".env"

if (-not (Test-Path $launcher)) {
    Write-Host "NapCat Shell launcher was not found."
    Write-Host "Expected: $launcher"
    exit 1
}

if (-not $QQNumber -and (Test-Path $envFile)) {
    $line = Select-String -Path $envFile -Pattern "^NAPCAT_QQ=" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($line) {
        $QQNumber = ($line.Line -replace "^NAPCAT_QQ=", "").Trim()
    }
}

if ($QQNumber) {
    Start-Process -FilePath $launcher -ArgumentList $QQNumber -WorkingDirectory $napcatDir
    exit 0
}

Start-Process -FilePath $launcher -WorkingDirectory $napcatDir
