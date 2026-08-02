<#
.SYNOPSIS
    Installs or rolls back the explicit MCP bridge for Browser (Pinned Personal).

.DESCRIPTION
    ProcessScan and Preflight are read-only. Install and Rollback must be run
    from an independent PowerShell window. The script waits until every Codex
    process and descendant has exited and remained stopped for five seconds.
#>
[CmdletBinding()]
param(
    [ValidateSet("ProcessScan", "Preflight", "Install", "Rollback")]
    [string]$Mode = "Preflight",
    [int]$WaitTimeoutSeconds = 900,
    [ValidateRange(3, 30)]
    [int]$StableSeconds = 5,
    [string]$BackupPath = "",
    [switch]$ConfirmInstall,
    [switch]$ConfirmRollback
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script:StageRoot = Join-Path $script:RepoRoot "tmp\personal-plugin-mcp-bridge-stage\browser-pinned"
$script:PersonalRoot = Join-Path $env:USERPROFILE "plugins\browser-pinned"
$script:BackupRoot = Join-Path $script:RepoRoot "backups\codex-browser-mcp-bridge"
$script:LogRoot = Join-Path $script:RepoRoot "logs"
$script:ExpectedDesktopVersion = "26.715.8383.0"
$script:ExpectedPluginVersion = "26.715.61943+codex.20260721132709"
$script:ExpectedNodeReplHash = "5419A4DBA576A319EB33D848131ACECA62AC189224211C84C0ECD932A8310CB8"
$script:ExpectedBrowserHash = "0B03C76C1D0F3D4C81F89F58FF210AE6709FD1204D2C5A4FDFFA0A7BDB961B96"
$script:RunStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:LockStream = $null

New-Item -ItemType Directory -Force -Path $script:LogRoot | Out-Null
$script:LogPath = Join-Path $script:LogRoot ("codex-browser-mcp-bridge-{0}-{1}.log" -f $Mode.ToLowerInvariant(), $script:RunStamp)

function Write-BridgeLog {
    param(
        [ValidateSet("INFO", "OK", "WARN", "ERROR")]
        [string]$Level,
        [string]$Message
    )
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $Level, $Message
    [System.IO.File]::AppendAllText($script:LogPath, $line + [Environment]::NewLine, $script:Utf8NoBom)
    $color = "Gray"
    if ($Level -eq "OK") { $color = "Green" }
    if ($Level -eq "WARN") { $color = "Yellow" }
    if ($Level -eq "ERROR") { $color = "Red" }
    Write-Host $line -ForegroundColor $color
}

function Read-Utf8Json {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing JSON file: $Path" }
    return ([System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8) | ConvertFrom-Json)
}

function Get-Hash {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing file: $Path" }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Get-AllProcessInfo {
    return @(Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object {
        [pscustomobject]@{
            Name = [string]$_.Name
            ProcessId = [int]$_.ProcessId
            ParentProcessId = [int]$_.ParentProcessId
            ExecutablePath = [string]$_.ExecutablePath
            CommandLine = [string]$_.CommandLine
            Reason = ""
        }
    })
}

function Get-CodexReason {
    param([object]$Process)
    $name = ([string]$Process.Name).ToLowerInvariant()
    $text = ((@($Process.Name, $Process.ExecutablePath, $Process.CommandLine) -join " ").Replace("/", "\")).ToLowerInvariant()
    if (@("codex.exe", "codex-code-mode-host.exe", "codex-command-runner.exe", "codex-computer-use.exe", "node_repl.exe", "chatgpt.exe", "openai.codex.exe") -contains $name) {
        if ($name -ne "chatgpt.exe" -or $text.Contains("\windowsapps\openai.codex_")) { return "Codex executable" }
    }
    foreach ($marker in @(
        "\windowsapps\openai.codex_",
        "\packages\openai.codex_",
        "\appdata\roaming\npm\node_modules\@openai\codex\",
        "\appdata\local\openai\codex\runtimes\",
        "\localcache\local\codex\",
        "\localcache\roaming\codex\web\codex\"
    )) {
        if ($text.Contains($marker)) { return "Codex path marker" }
    }
    return ""
}

function Get-CodexProcesses {
    $all = @(Get-AllProcessInfo)
    $selected = @{}
    foreach ($process in $all) {
        $reason = Get-CodexReason -Process $process
        if (-not [string]::IsNullOrWhiteSpace($reason)) {
            $process.Reason = $reason
            $selected[$process.ProcessId] = $process
        }
    }
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($process in $all) {
            if (-not $selected.ContainsKey($process.ProcessId) -and $selected.ContainsKey($process.ParentProcessId)) {
                $process.Reason = "Descendant of PID $($process.ParentProcessId)"
                $selected[$process.ProcessId] = $process
                $changed = $true
            }
        }
    }
    return @($selected.Values | Sort-Object ProcessId)
}

function Get-Ancestors {
    $all = @(Get-AllProcessInfo)
    $byId = @{}
    foreach ($process in $all) { $byId[$process.ProcessId] = $process }
    $result = @()
    $id = $PID
    $seen = @{}
    while ($byId.ContainsKey($id) -and -not $seen.ContainsKey($id)) {
        $seen[$id] = $true
        $current = $byId[$id]
        $result += $current
        if ($current.ParentProcessId -le 0) { break }
        $id = $current.ParentProcessId
    }
    return $result
}

function Test-InsideCodex {
    foreach ($process in @(Get-Ancestors)) {
        if ($process.ProcessId -eq $PID) { continue }
        if (-not [string]::IsNullOrWhiteSpace((Get-CodexReason -Process $process))) { return $true }
    }
    return $false
}

function Write-ProcessList {
    param([object[]]$Processes)
    if ($Processes.Count -eq 0) {
        Write-BridgeLog -Level "OK" -Message "NO_CODEX_PROCESS_DETECTED"
        return
    }
    Write-BridgeLog -Level "WARN" -Message ("CODEX_PROCESS_COUNT={0}" -f $Processes.Count)
    foreach ($process in $Processes) {
        Write-BridgeLog -Level "WARN" -Message ("PID={0} PPID={1} NAME={2} REASON={3}" -f $process.ProcessId, $process.ParentProcessId, $process.Name, $process.Reason)
    }
}

function Wait-CodexExit {
    $deadline = (Get-Date).AddSeconds($WaitTimeoutSeconds)
    $stableSince = $null
    $lastSignature = ""
    while ((Get-Date) -lt $deadline) {
        $processes = @(Get-CodexProcesses)
        $signature = (($processes | ForEach-Object { "{0}:{1}:{2}" -f $_.ProcessId, $_.ParentProcessId, $_.Name }) -join "|")
        if ($processes.Count -gt 0) {
            if ($signature -ne $lastSignature) { Write-ProcessList -Processes $processes }
            $lastSignature = $signature
            $stableSince = $null
        } else {
            if ($null -eq $stableSince) {
                $stableSince = Get-Date
                Write-BridgeLog -Level "INFO" -Message ("VERIFYING_STABLE_EXIT_{0}_SECONDS" -f $StableSeconds)
            }
            if (((Get-Date) - $stableSince).TotalSeconds -ge $StableSeconds) {
                Write-BridgeLog -Level "OK" -Message "CODEX_EXIT_CONFIRMED"
                return
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out while waiting for all Codex processes to exit."
}

function Get-PluginPython {
    foreach ($path in @(
        (Join-Path $script:RepoRoot ".venv\Scripts\python.exe"),
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    )) {
        if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    }
    throw "Plugin validation Python is unavailable."
}

function Validate-Plugin {
    param([string]$Root)
    $python = Get-PluginPython
    $validator = Join-Path $env:USERPROFILE ".codex\skills\.system\plugin-creator\scripts\validate_plugin.py"
    $output = & $python $validator $Root 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Plugin validation failed: $output" }
}

function Get-MarketplaceName {
    $python = Get-PluginPython
    $reader = Join-Path $env:USERPROFILE ".codex\skills\.system\plugin-creator\scripts\read_marketplace_name.py"
    $name = (& $python $reader 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($name)) { throw "Unable to read personal marketplace name." }
    return $name
}

function Get-CodexCommand {
    foreach ($name in @("codex.cmd", "codex.exe", "codex")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    throw "Codex CLI is unavailable."
}

function Copy-Exact {
    param([string]$Source, [string]$Destination, [string]$Label)
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { throw "$Label source is missing: $Source" }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy.exe $Source $Destination /MIR /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NP /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "$Label copy failed with robocopy exit code $LASTEXITCODE" }
}

function Enter-Lock {
    New-Item -ItemType Directory -Force -Path $script:BackupRoot | Out-Null
    try {
        $script:LockStream = New-Object System.IO.FileStream((Join-Path $script:BackupRoot "bridge.lock"), [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    } catch { throw "Another Browser MCP bridge operation is already running." }
}

function Exit-Lock {
    if ($null -ne $script:LockStream) {
        $script:LockStream.Dispose()
        $script:LockStream = $null
    }
}

function Invoke-Preflight {
    $package = @(Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction Stop | Where-Object { [string]$_.Version -eq $script:ExpectedDesktopVersion })
    if ($package.Count -eq 0) { throw "Codex Desktop $($script:ExpectedDesktopVersion) is not registered." }

    $manifest = Read-Utf8Json -Path (Join-Path $script:StageRoot ".codex-plugin\plugin.json")
    if ([string]$manifest.name -ne "browser-pinned" -or [string]$manifest.version -ne $script:ExpectedPluginVersion) { throw "Unexpected bridge plugin manifest." }
    if ([string]$manifest.mcpServers -ne "./.mcp.json") { throw "Bridge plugin does not declare .mcp.json." }

    $mcp = Read-Utf8Json -Path (Join-Path $script:StageRoot ".mcp.json")
    $nodeRepl = [string]$mcp.mcpServers.node_repl.command
    if (-not (Test-Path -LiteralPath $nodeRepl -PathType Leaf)) { throw "Bridge runtime is missing: $nodeRepl" }
    if ((Get-Hash -Path $nodeRepl) -ne $script:ExpectedNodeReplHash) { throw "Bridge runtime hash mismatch." }
    if ((Get-Hash -Path (Join-Path $script:StageRoot "scripts\browser-client.mjs")) -ne $script:ExpectedBrowserHash) { throw "Browser client hash mismatch." }
    $help = & $nodeRepl --help 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $help -notmatch "node_repl MCP stdio server") { throw "Bridge runtime self-test failed." }

    Validate-Plugin -Root $script:StageRoot
    $marketplace = Read-Utf8Json -Path (Join-Path $env:USERPROFILE ".agents\plugins\marketplace.json")
    if (@($marketplace.plugins | Where-Object { [string]$_.name -eq "browser-pinned" }).Count -ne 1) { throw "Personal marketplace browser-pinned entry is missing or duplicated." }

    Write-ProcessList -Processes @(Get-CodexProcesses)
    if (Test-InsideCodex) {
        Write-BridgeLog -Level "WARN" -Message "RUN_CONTEXT=INSIDE_CODEX_PROCESS_TREE"
    } else {
        Write-BridgeLog -Level "OK" -Message "RUN_CONTEXT=INDEPENDENT_POWERSHELL"
    }
    Write-BridgeLog -Level "INFO" -Message ("BRIDGE_PLUGIN_VERSION={0}" -f $script:ExpectedPluginVersion)
    Write-BridgeLog -Level "OK" -Message "BROWSER_MCP_BRIDGE_PREFLIGHT_OK"
}

function New-Backup {
    New-Item -ItemType Directory -Force -Path $script:BackupRoot | Out-Null
    $backup = Join-Path $script:BackupRoot $script:RunStamp
    if (Test-Path -LiteralPath $backup) { throw "Backup already exists: $backup" }
    New-Item -ItemType Directory -Path $backup | Out-Null
    Copy-Exact -Source $script:PersonalRoot -Destination (Join-Path $backup "personal-plugin-source") -Label "Personal Browser backup"
    foreach ($item in @(
        @{ Source = (Join-Path $env:USERPROFILE ".codex\config.toml"); Name = "config.toml" },
        @{ Source = (Join-Path $env:USERPROFILE ".agents\plugins\marketplace.json"); Name = "marketplace.json" }
    )) {
        if (Test-Path -LiteralPath $item.Source -PathType Leaf) { Copy-Item -LiteralPath $item.Source -Destination (Join-Path $backup $item.Name) -Force }
    }
    $oldManifest = Read-Utf8Json -Path (Join-Path $script:PersonalRoot ".codex-plugin\plugin.json")
    $data = [ordered]@{
        CreatedAt = (Get-Date).ToString("o")
        BackupPath = $backup
        PreviousPluginVersion = [string]$oldManifest.version
        PreviousBrowserHash = Get-Hash -Path (Join-Path $script:PersonalRoot "scripts\browser-client.mjs")
        BridgePluginVersion = $script:ExpectedPluginVersion
    }
    [System.IO.File]::WriteAllText((Join-Path $backup "bridge-manifest.json"), ($data | ConvertTo-Json -Depth 5), $script:Utf8NoBom)
    Write-BridgeLog -Level "OK" -Message "BROWSER_MCP_BRIDGE_BACKUP_OK"
    Write-BridgeLog -Level "INFO" -Message ("BACKUP_PATH={0}" -f $backup)
    return $backup
}

function Install-PluginFromSource {
    param([string]$Source, [string]$ExpectedVersion, [string]$ExpectedBrowserHash)
    Copy-Exact -Source $Source -Destination $script:PersonalRoot -Label "Personal Browser install"
    Validate-Plugin -Root $script:PersonalRoot
    if ((Get-Hash -Path (Join-Path $script:PersonalRoot "scripts\browser-client.mjs")) -ne $ExpectedBrowserHash) { throw "Installed Browser source hash mismatch." }

    $marketplaceName = Get-MarketplaceName
    $codex = Get-CodexCommand
    $output = & $codex plugin add ("browser-pinned@{0}" -f $marketplaceName) --json 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "codex plugin add failed: $output" }

    $cacheRoot = Join-Path $env:USERPROFILE ".codex\plugins\cache\$marketplaceName\browser-pinned"
    $match = $null
    foreach ($directory in @(Get-ChildItem -LiteralPath $cacheRoot -Directory -ErrorAction Stop | Sort-Object LastWriteTime -Descending)) {
        $candidate = Join-Path $directory.FullName ".codex-plugin\plugin.json"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            if ([string](Read-Utf8Json -Path $candidate).version -eq $ExpectedVersion) { $match = $directory.FullName; break }
        }
    }
    if ($null -eq $match) { throw "Installed plugin cache version $ExpectedVersion was not found." }
    if ((Get-Hash -Path (Join-Path $match "scripts\browser-client.mjs")) -ne $ExpectedBrowserHash) { throw "Installed Browser cache hash mismatch." }
    return $match
}

function Invoke-Install {
    if (-not $ConfirmInstall) { throw "Install mode requires -ConfirmInstall." }
    if (Test-InsideCodex) { throw "Install must be started from an independent PowerShell window." }
    Enter-Lock
    $backup = $null
    try {
        Invoke-Preflight
        Wait-CodexExit
        $backup = New-Backup
        [void](Install-PluginFromSource -Source $script:StageRoot -ExpectedVersion $script:ExpectedPluginVersion -ExpectedBrowserHash $script:ExpectedBrowserHash)
        Write-BridgeLog -Level "OK" -Message "BROWSER_MCP_BRIDGE_INSTALL_OK"
        Write-BridgeLog -Level "OK" -Message "CONVERSATION_DATA_PRESERVED"
        Write-BridgeLog -Level "OK" -Message "SAFE_TO_REOPEN_CODEX"
    } catch {
        Write-BridgeLog -Level "ERROR" -Message $_.Exception.Message
        if ($null -ne $backup) {
            try {
                $rollbackManifest = Read-Utf8Json -Path (Join-Path $backup "bridge-manifest.json")
                [void](Install-PluginFromSource -Source (Join-Path $backup "personal-plugin-source") -ExpectedVersion ([string]$rollbackManifest.PreviousPluginVersion) -ExpectedBrowserHash ([string]$rollbackManifest.PreviousBrowserHash))
                Write-BridgeLog -Level "OK" -Message "BROWSER_MCP_BRIDGE_AUTO_ROLLBACK_OK"
            } catch {
                Write-BridgeLog -Level "ERROR" -Message ("Automatic rollback failed: {0}" -f $_.Exception.Message)
            }
        }
        Write-BridgeLog -Level "ERROR" -Message "BROWSER_MCP_BRIDGE_INSTALL_FAILED"
        throw
    } finally { Exit-Lock }
}

function Find-Backup {
    if (-not [string]::IsNullOrWhiteSpace($BackupPath)) { return [System.IO.Path]::GetFullPath($BackupPath) }
    $candidate = Get-ChildItem -LiteralPath $script:BackupRoot -Directory -ErrorAction Stop | Sort-Object Name -Descending | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName "bridge-manifest.json") -PathType Leaf
    } | Select-Object -First 1
    if ($null -eq $candidate) { throw "No Browser MCP bridge backup was found." }
    return $candidate.FullName
}

function Invoke-Rollback {
    if (-not $ConfirmRollback) { throw "Rollback mode requires -ConfirmRollback." }
    if (Test-InsideCodex) { throw "Rollback must be started from an independent PowerShell window." }
    Enter-Lock
    try {
        $backup = Find-Backup
        $manifest = Read-Utf8Json -Path (Join-Path $backup "bridge-manifest.json")
        Wait-CodexExit
        [void](Install-PluginFromSource -Source (Join-Path $backup "personal-plugin-source") -ExpectedVersion ([string]$manifest.PreviousPluginVersion) -ExpectedBrowserHash ([string]$manifest.PreviousBrowserHash))
        Write-BridgeLog -Level "OK" -Message "BROWSER_MCP_BRIDGE_ROLLBACK_OK"
        Write-BridgeLog -Level "OK" -Message "CONVERSATION_DATA_PRESERVED"
        Write-BridgeLog -Level "OK" -Message "SAFE_TO_REOPEN_CODEX"
    } catch {
        Write-BridgeLog -Level "ERROR" -Message $_.Exception.Message
        Write-BridgeLog -Level "ERROR" -Message "BROWSER_MCP_BRIDGE_ROLLBACK_FAILED"
        throw
    } finally { Exit-Lock }
}

try {
    Write-BridgeLog -Level "INFO" -Message ("MODE={0} PID={1}" -f $Mode, $PID)
    switch ($Mode) {
        "ProcessScan" {
            Write-ProcessList -Processes @(Get-CodexProcesses)
            if (Test-InsideCodex) { Write-BridgeLog -Level "WARN" -Message "RUN_CONTEXT=INSIDE_CODEX_PROCESS_TREE" }
            else { Write-BridgeLog -Level "OK" -Message "RUN_CONTEXT=INDEPENDENT_POWERSHELL" }
            Write-BridgeLog -Level "OK" -Message "PROCESS_SCAN_OK"
        }
        "Preflight" { Invoke-Preflight }
        "Install" { Invoke-Install }
        "Rollback" { Invoke-Rollback }
    }
    Write-BridgeLog -Level "INFO" -Message ("LOG_PATH={0}" -f $script:LogPath)
} catch {
    Write-BridgeLog -Level "ERROR" -Message $_.Exception.Message
    Write-BridgeLog -Level "ERROR" -Message ("FAILED_LOG_PATH={0}" -f $script:LogPath)
    Exit-Lock
    exit 1
}
