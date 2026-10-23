param(
    [switch]$SkipOllamaEnsure
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$botEntry = Join-Path $RepoRoot "bot.py"

Set-Location -LiteralPath $RepoRoot

function Get-BotPort {
    param([object]$ConfigurationReport)
    return [int]$ConfigurationReport.nonebot_port
}

function Get-PortListener {
    param([int]$LocalPort)

    $connections = @()
    try {
        $connections = @(
            Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction Stop
        )
    } catch {
        $connections = @()
    }

    $owningProcessIds = @(
        $connections |
            ForEach-Object { [int]$_.OwningProcess }
    )
    if ($owningProcessIds.Count -eq 0) {
        try {
            $netstatLines = & netstat.exe -ano -p tcp 2>$null
            foreach ($line in $netstatLines) {
                if (
                    $line -match '^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$' -and
                    [int]$Matches[1] -eq $LocalPort
                ) {
                    $owningProcessIds += [int]$Matches[2]
                }
            }
        } catch {
            $owningProcessIds = @()
        }
    }

    $listeners = @()
    foreach ($processId in ($owningProcessIds | Sort-Object -Unique)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if (-not $process -or [string]::IsNullOrWhiteSpace([string]$process.CommandLine)) {
            $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
            if ($wmiProcess) {
                $process = $wmiProcess
            }
        }
        if (-not $process -or [string]::IsNullOrWhiteSpace([string]$process.CommandLine)) {
            $process = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object { $_.ProcessId -eq $processId } |
                Select-Object -First 1
        }
        if (-not $process) {
            $fallbackProcess = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($fallbackProcess) {
                $process = [pscustomobject]@{
                    Name = "$($fallbackProcess.ProcessName).exe"
                    ExecutablePath = $fallbackProcess.Path
                    CommandLine = ""
                }
            }
        }
        $listeners += [pscustomobject]@{
            ProcessId = $processId
            ParentProcessId = $process.ParentProcessId
            Name = $process.Name
            ExecutablePath = $process.ExecutablePath
            CommandLine = $process.CommandLine
        }
    }
    return @($listeners)
}

function Test-ChatbotProcess {
    param([object]$ProcessInfo)

    if ($ProcessInfo.Name -notlike "python*") {
        return $false
    }
    if (
        [string]::Equals(
            [string]$ProcessInfo.ExecutablePath,
            $python,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        return $true
    }
    $parentProcessId = 0
    if ([int]::TryParse([string]$ProcessInfo.ParentProcessId, [ref]$parentProcessId)) {
        $parentProcess = Get-Process -Id $parentProcessId -ErrorAction SilentlyContinue
        if (
            $parentProcess -and
            $parentProcess.ProcessName -like "python*" -and
            [string]::Equals(
                [string]$parentProcess.Path,
                $python,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            return $true
        }
    }
    $commandLine = [string]$ProcessInfo.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine) -or $commandLine -notlike "*bot.py*") {
        return $false
    }
    return (
        $commandLine.IndexOf($botEntry, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $commandLine.IndexOf($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Virtual environment not found. Run .\scripts\setup.ps1 first."
    exit 1
}

$configurationJson = & $python (Join-Path $PSScriptRoot "check_configuration.py") --json
if ($LASTEXITCODE -ne 0) {
    Write-Host ($configurationJson -join "`n")
    exit 1
}
$configurationReport = ($configurationJson -join "`n") | ConvertFrom-Json
if (-not $configurationReport.persona_bindings.ready) {
    Write-Host "Fixed persona bindings are invalid. Check BOT_PERSONA_BINDINGS, role cards and routing configuration."
    exit 1
}
if ($configurationReport.issues.Count -gt 0) {
    foreach ($issue in $configurationReport.issues) {
        Write-Host ("Configuration {0}: {1} ({2})" -f $issue.severity, $issue.key, $issue.message)
    }
}

$botPort = Get-BotPort $configurationReport

$listeners = @(Get-PortListener -LocalPort $botPort)
if ($listeners.Count -gt 0) {
    $chatbotListeners = @($listeners | Where-Object { Test-ChatbotProcess $_ })
    if ($chatbotListeners.Count -gt 0) {
        Write-Host "QQ Chatbot is already running on 127.0.0.1:$botPort."
        $chatbotListeners | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | Format-List
        exit 0
    }

    Write-Host "Port $botPort is already in use by another process."
    $listeners | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | Format-List
    exit 1
}


if ($configurationReport.ollama_auto_ensure -and -not $SkipOllamaEnsure -and $env:SKIP_OLLAMA_ENSURE -notin @("1", "true", "yes", "on")) {
    foreach ($plan in $configurationReport.ollama_local_plans) {
        if (-not $plan.standard_local) { continue }
        $ensureArguments = @{ BaseUrl = $plan.base_url; RequiredModels = @($plan.models) }
        & .\scripts\ensure-ollama.ps1 @ensureArguments
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

& $python $botEntry
