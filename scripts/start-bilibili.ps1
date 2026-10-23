param(
    [switch]$Background,
    [switch]$PreviewOnly,
    [switch]$Once
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = "utf-8"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$browserEntry = Join-Path $RepoRoot "scripts\bilibili_browser.py"
$workerEntry = Join-Path $RepoRoot "scripts\bilibili_autobrowse.py"
$inboxEntry = Join-Path $RepoRoot "scripts\bilibili_inbox.py"
$withInbox = -not $PreviewOnly -and -not $Once
Set-Location -LiteralPath $RepoRoot

function Start-CompanionInbox {
    if ($withInbox) {
        & (Join-Path $PSScriptRoot "start-bilibili-inbox.ps1") -Background
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python is missing: $python"
}

$statusLines = @(& $python $workerEntry status)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($statusLines.Count -gt 0) {
    $currentStatus = $statusLines[0] | ConvertFrom-Json
    if ($currentStatus.running) {
        Start-CompanionInbox
        Write-Host "Bilibili worker is already running. Stop it before changing modes."
        $statusLines | ForEach-Object { Write-Host $_ }
        exit 0
    }
}

& $python $browserEntry open
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python $browserEntry check
if ($LASTEXITCODE -ne 0) {
    Write-Host "Log in to the dedicated Edge window, then run this command again."
    exit $LASTEXITCODE
}
& $python $workerEntry init
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Start-CompanionInbox

$workerArgs = @("-u", $workerEntry, "run")
if (-not $PreviewOnly) { $workerArgs += "--send" }
if ($Once) { $workerArgs += "--once" }

if ($Background) {
    $privateHome = $env:AIKE_BILIBILI_HOME
    if ([string]::IsNullOrWhiteSpace($privateHome)) {
        $privateHome = Join-Path $env:LOCALAPPDATA "AIchatbot\bilibili"
    }
    $privateHome = [System.IO.Path]::GetFullPath($privateHome)
    New-Item -ItemType Directory -Path $privateHome -Force | Out-Null
    $launchArgs = @("-u", ('"{0}"' -f $workerEntry), "run")
    if (-not $PreviewOnly) { $launchArgs += "--send" }
    if ($Once) { $launchArgs += "--once" }
    $process = Start-Process -FilePath $python -ArgumentList $launchArgs -WorkingDirectory $RepoRoot `
        -WindowStyle Hidden -RedirectStandardOutput (Join-Path $privateHome "autobrowse.stdout.log") `
        -RedirectStandardError (Join-Path $privateHome "autobrowse.stderr.log") -PassThru
    if ($process.WaitForExit(1500) -and -not $Once) {
        throw "Worker exited during startup. Check autobrowse.stderr.log and run status."
    }
    & $python $workerEntry status
} else {
    Write-Host "Bilibili worker is running in this terminal. Keep it open; Ctrl+C stops browsing and its companion inbox."
    $workerExit = 0
    try {
        & $python @workerArgs
        $workerExit = $LASTEXITCODE
    } finally {
        if ($withInbox) { & $python $inboxEntry stop }
    }
    exit $workerExit
}
