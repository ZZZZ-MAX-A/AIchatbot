param(
    [int]$Port = 8090,
    [string]$HostAddress = "127.0.0.1",
    [string]$StaticDir = "web/owner-console/dist",
    [switch]$Build,
    [switch]$Foreground,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $RepoRoot

function Get-PortListener {
    param([int]$LocalPort)

    try {
        $connections = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction Stop
    } catch {
        return @()
    }

    $listeners = @()
    foreach ($connection in $connections) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
        $listeners += [pscustomobject]@{
            ProcessId = $connection.OwningProcess
            Name = $process.Name
            CommandLine = $process.CommandLine
        }
    }
    return $listeners
}

function Test-OwnerConsoleProcess {
    param([object]$ProcessInfo)

    return $ProcessInfo.CommandLine -like "*src.owner_console_fastapi_launcher:app*"
}

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not found. Run .\scripts\setup.ps1 first."
    exit 1
}

$listeners = @(Get-PortListener -LocalPort $Port)
if ($listeners.Count -gt 0) {
    $ownerListeners = @($listeners | Where-Object { Test-OwnerConsoleProcess $_ })
    if ($ownerListeners.Count -gt 0) {
        Write-Host "Owner Console is already running on http://$HostAddress`:$Port/owner-console"
        $ownerListeners | Select-Object ProcessId,Name,CommandLine | Format-List
        exit 0
    }

    Write-Host "Port $Port is already in use by another process."
    $listeners | Select-Object ProcessId,Name,CommandLine | Format-List
    exit 1
}

$staticPath = if ([System.IO.Path]::IsPathRooted($StaticDir)) {
    $StaticDir
} else {
    Join-Path $RepoRoot $StaticDir
}
$indexFile = Join-Path $staticPath "index.html"

if (-not (Test-Path $indexFile)) {
    if ($Build) {
        $frontendRoot = Join-Path $RepoRoot "web\owner-console"
        if (-not (Test-Path (Join-Path $frontendRoot "package.json"))) {
            Write-Host "Owner Console frontend package.json not found."
            exit 1
        }

        Write-Host "Static build not found. Running npm run build..."
        Push-Location $frontendRoot
        try {
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) {
                exit $LASTEXITCODE
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "Static build not found: $indexFile"
        Write-Host "Run:"
        Write-Host "  cd $RepoRoot\web\owner-console"
        Write-Host "  npm run build"
        Write-Host "Or run this script with -Build."
        exit 1
    }
}

if (-not (Test-Path $indexFile)) {
    Write-Host "Static build is still missing after build attempt: $indexFile"
    exit 1
}

if ($CheckOnly) {
    Write-Host "Owner Console start preflight OK."
    Write-Host "Static dir: $staticPath"
    Write-Host "URL: http://$HostAddress`:$Port/owner-console"
    exit 0
}

$logDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "owner-console.out.log"
$errLog = Join-Path $logDir "owner-console.err.log"

$env:OWNER_CONSOLE_STATIC_ENABLED = "true"
$env:OWNER_CONSOLE_STATIC_DIR = $StaticDir

$arguments = @(
    "-m",
    "uvicorn",
    "src.owner_console_fastapi_launcher:app",
    "--host",
    $HostAddress,
    "--port",
    "$Port"
)

if ($Foreground) {
    Write-Host "Starting Owner Console in foreground:"
    Write-Host "  http://$HostAddress`:$Port/owner-console"
    & $python @arguments
    exit $LASTEXITCODE
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList $arguments `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 2

$startedListeners = @(Get-PortListener -LocalPort $Port | Where-Object { Test-OwnerConsoleProcess $_ })
if ($startedListeners.Count -eq 0) {
    Write-Host "Owner Console failed to start. Check logs:"
    Write-Host "  $outLog"
    Write-Host "  $errLog"
    exit 1
}

Write-Host "Owner Console started."
Write-Host "URL: http://$HostAddress`:$Port/owner-console"
Write-Host "ProcessId: $($process.Id)"
Write-Host "Logs:"
Write-Host "  $outLog"
Write-Host "  $errLog"
