<#
.SYNOPSIS
    Performs a controlled, logged repair of the Codex Desktop Browser plugin.

.DESCRIPTION
    ProcessScan and Preflight are read-only. Repair and Rollback must be started
    from an independent PowerShell window. The script never terminates Codex;
    it lists every detected Codex process and waits until the complete process
    tree has remained stopped for a stable interval.

.EXAMPLE
    .\scripts\repair-codex-browser.ps1 -Mode ProcessScan

.EXAMPLE
    .\scripts\repair-codex-browser.ps1 -Mode Preflight

.EXAMPLE
    .\scripts\repair-codex-browser.ps1 -Mode Repair -ConfirmRepair

.EXAMPLE
    .\scripts\repair-codex-browser.ps1 -Mode Rollback -BackupPath "C:\Users\me\.codex\browser-repair-backups\20260721-120000" -ConfirmRollback
#>
[CmdletBinding()]
param(
    [ValidateSet("ProcessScan", "Preflight", "Repair", "Rollback")]
    [string]$Mode = "Preflight",

    [int]$WaitTimeoutSeconds = 900,

    [ValidateRange(3, 30)]
    [int]$StableSeconds = 5,

    [string]$BackupPath = "",

    [switch]$ConfirmRepair,

    [switch]$ConfirmRollback,

    [switch]$RepairConfigSource
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script:LogDirectory = Join-Path $script:RepoRoot "logs"
$script:LogFallbackActivated = $false
try {
    New-Item -ItemType Directory -Force -Path $script:LogDirectory | Out-Null
} catch {
    $script:LogDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "codex-browser-repair-logs"
    New-Item -ItemType Directory -Force -Path $script:LogDirectory | Out-Null
    $script:LogFallbackActivated = $true
}

$script:RunStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$script:LogPath = Join-Path $script:LogDirectory ("codex-browser-repair-{0}-{1}.log" -f $Mode.ToLowerInvariant(), $script:RunStamp)
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:LockStream = $null

function Write-RepairLog {
    param(
        [ValidateSet("INFO", "OK", "WARN", "ERROR")]
        [string]$Level,
        [string]$Message
    )

    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $Level, $Message
    try {
        [System.IO.File]::AppendAllText($script:LogPath, $line + [Environment]::NewLine, $script:Utf8NoBom)
    } catch {
        if ($script:LogFallbackActivated) {
            throw
        }

        $fallbackDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "codex-browser-repair-logs"
        New-Item -ItemType Directory -Force -Path $fallbackDirectory | Out-Null
        $script:LogDirectory = $fallbackDirectory
        $script:LogPath = Join-Path $fallbackDirectory ("codex-browser-repair-{0}-{1}.log" -f $Mode.ToLowerInvariant(), $script:RunStamp)
        $script:LogFallbackActivated = $true
        [System.IO.File]::AppendAllText(
            $script:LogPath,
            (("{0} [WARN] Preferred workspace log path was not writable; using TEMP fallback." -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff")) + [Environment]::NewLine),
            $script:Utf8NoBom
        )
        [System.IO.File]::AppendAllText($script:LogPath, $line + [Environment]::NewLine, $script:Utf8NoBom)
    }

    $color = "Gray"
    if ($Level -eq "OK") { $color = "Green" }
    if ($Level -eq "WARN") { $color = "Yellow" }
    if ($Level -eq "ERROR") { $color = "Red" }
    Write-Host $line -ForegroundColor $color
}

function Write-Step {
    param(
        [int]$Current,
        [int]$Total,
        [string]$Name
    )

    Write-RepairLog -Level "INFO" -Message ("[{0}/{1}] {2}" -f $Current, $Total, $Name)
}

function Get-NormalizedProcessText {
    param([object]$ProcessInfo)

    $parts = @($ProcessInfo.Name, $ProcessInfo.ExecutablePath, $ProcessInfo.CommandLine)
    return (($parts -join " ").Replace("/", "\")).ToLowerInvariant()
}

function Get-CodexSignatureReason {
    param([object]$ProcessInfo)

    $name = ([string]$ProcessInfo.Name).ToLowerInvariant()
    $text = Get-NormalizedProcessText -ProcessInfo $ProcessInfo

    $exactNames = @(
        "codex.exe",
        "codex-code-mode-host.exe",
        "codex-computer-use.exe",
        "node_repl.exe",
        "openai.codex.exe",
        "codex-desktop.exe"
    )
    if ($exactNames -contains $name) {
        return "codex executable name"
    }

    $pathMarkers = @(
        "\windowsapps\openai.codex_",
        "\appdata\roaming\npm\node_modules\@openai\codex\",
        "\appdata\local\openai\codex\runtimes\",
        "\localcache\roaming\codex\web\codex\",
        "\localcache\local\codex\"
    )
    foreach ($marker in $pathMarkers) {
        if ($text.Contains($marker)) {
            return "Codex path marker: $marker"
        }
    }

    if ($name -eq "node.exe" -and $text -match "@openai\\codex\\bin\\codex\.js") {
        return "npm Codex launcher"
    }

    return ""
}

function Get-AllProcessInfo {
    return @(Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object {
        [pscustomobject]@{
            Name = [string]$_.Name
            ProcessId = [int]$_.ProcessId
            ParentProcessId = [int]$_.ParentProcessId
            CreationDate = $_.CreationDate
            ExecutablePath = [string]$_.ExecutablePath
            CommandLine = [string]$_.CommandLine
            MatchReason = ""
        }
    })
}

function Get-CodexProcessInventory {
    $all = @(Get-AllProcessInfo)
    $selected = @{}

    foreach ($process in $all) {
        $reason = Get-CodexSignatureReason -ProcessInfo $process
        if (-not [string]::IsNullOrWhiteSpace($reason)) {
            $process.MatchReason = $reason
            $selected[$process.ProcessId] = $process
        }
    }

    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($process in $all) {
            if (-not $selected.ContainsKey($process.ProcessId) -and $selected.ContainsKey($process.ParentProcessId)) {
                $process.MatchReason = "descendant of PID $($process.ParentProcessId)"
                $selected[$process.ProcessId] = $process
                $changed = $true
            }
        }
    }

    return @($selected.Values | Sort-Object ProcessId)
}

function Get-CurrentProcessAncestors {
    $all = @(Get-AllProcessInfo)
    $byId = @{}
    foreach ($process in $all) {
        $byId[$process.ProcessId] = $process
    }

    $result = @()
    $currentId = $PID
    $visited = @{}
    while ($byId.ContainsKey($currentId) -and -not $visited.ContainsKey($currentId)) {
        $visited[$currentId] = $true
        $current = $byId[$currentId]
        $result += $current
        if ($current.ParentProcessId -le 0) {
            break
        }
        $currentId = $current.ParentProcessId
    }
    return $result
}

function Test-RunningInsideCodex {
    $ancestors = @(Get-CurrentProcessAncestors)
    foreach ($process in $ancestors) {
        if ($process.ProcessId -eq $PID) {
            continue
        }
        $reason = Get-CodexSignatureReason -ProcessInfo $process
        if (-not [string]::IsNullOrWhiteSpace($reason)) {
            return $true
        }
    }
    return $false
}

function Get-DisplayCommandLine {
    param([string]$CommandLine)

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return ""
    }
    if ($CommandLine.Length -le 180) {
        return $CommandLine
    }
    return $CommandLine.Substring(0, 177) + "..."
}

function Write-CodexProcessInventory {
    param([object[]]$Processes)

    if ($Processes.Count -eq 0) {
        Write-RepairLog -Level "OK" -Message "No Codex-related processes were detected."
        return
    }

    Write-RepairLog -Level "WARN" -Message ("Detected {0} Codex-related process(es)." -f $Processes.Count)
    foreach ($process in $Processes) {
        Write-RepairLog -Level "WARN" -Message (
            "PID={0} PPID={1} Name={2} Reason={3}" -f `
                $process.ProcessId,
                $process.ParentProcessId,
                $process.Name,
                $process.MatchReason
        )
        if (-not [string]::IsNullOrWhiteSpace($process.ExecutablePath)) {
            Write-RepairLog -Level "INFO" -Message ("  Path: {0}" -f $process.ExecutablePath)
        }
        $displayCommand = Get-DisplayCommandLine -CommandLine $process.CommandLine
        if (-not [string]::IsNullOrWhiteSpace($displayCommand)) {
            Write-RepairLog -Level "INFO" -Message ("  Cmd : {0}" -f $displayCommand)
        }
    }
}

function Wait-ForCodexExit {
    param(
        [int]$TimeoutSeconds,
        [int]$RequiredStableSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $stableSince = $null
    $lastSignature = ""

    while ((Get-Date) -lt $deadline) {
        $processes = @(Get-CodexProcessInventory)
        $signature = (($processes | ForEach-Object { "{0}:{1}:{2}" -f $_.ProcessId, $_.ParentProcessId, $_.Name }) -join "|")

        if ($processes.Count -gt 0) {
            $stableSince = $null
            if ($signature -ne $lastSignature) {
                Write-CodexProcessInventory -Processes $processes
                Write-RepairLog -Level "INFO" -Message "Close every Codex Desktop window and every Codex CLI session. This script will keep waiting."
                $lastSignature = $signature
            }
        } else {
            if ($null -eq $stableSince) {
                $stableSince = Get-Date
                Write-RepairLog -Level "INFO" -Message ("No Codex process detected. Verifying a {0}-second stable shutdown window..." -f $RequiredStableSeconds)
            }

            $stableFor = ((Get-Date) - $stableSince).TotalSeconds
            if ($stableFor -ge $RequiredStableSeconds) {
                Write-RepairLog -Level "OK" -Message "CODEX_EXIT_CONFIRMED"
                return
            }
        }

        Start-Sleep -Seconds 1
    }

    throw "Timed out after $TimeoutSeconds seconds while waiting for all Codex processes to exit."
}

function Enter-RepairLock {
    $lockPath = Join-Path ([System.IO.Path]::GetTempPath()) "codex-browser-controlled-repair.lock"
    try {
        $script:LockStream = New-Object System.IO.FileStream(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
        Write-RepairLog -Level "OK" -Message "Acquired exclusive repair lock: $lockPath"
    } catch {
        throw "Another Browser repair process may already be running. Lock: $lockPath"
    }
}

function Exit-RepairLock {
    if ($null -ne $script:LockStream) {
        $script:LockStream.Dispose()
        $script:LockStream = $null
    }
}

function Assert-PathUnderRoot {
    param(
        [string]$Path,
        [string]$Root,
        [string]$Label
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    if (-not $fullPath.StartsWith($fullRoot + "\", [System.StringComparison]::OrdinalIgnoreCase) -and
        -not $fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label is outside its allowed root. Path=$fullPath Root=$fullRoot"
    }
}

function Get-CodexLayout {
    $userProfile = [Environment]::GetFolderPath("UserProfile")
    $codexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        Join-Path $userProfile ".codex"
    } else {
        [System.IO.Path]::GetFullPath($env:CODEX_HOME)
    }

    $appPackages = @(Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction Stop | Sort-Object Version -Descending)
    if ($appPackages.Count -eq 0) {
        throw "OpenAI.Codex AppX package was not found for the current Windows user."
    }
    $appPackage = $appPackages[0]
    $installRoot = [string]$appPackage.InstallLocation
    if ([string]::IsNullOrWhiteSpace($installRoot) -or -not (Test-Path -LiteralPath $installRoot)) {
        throw "Codex Desktop install location is unavailable."
    }

    $bundledMarketplace = Join-Path $installRoot "app\resources\plugins\openai-bundled"
    $bundledManifest = Join-Path $bundledMarketplace ".agents\plugins\marketplace.json"
    $bundledBrowser = Join-Path $bundledMarketplace "plugins\browser"
    $bundledBrowserManifest = Join-Path $bundledBrowser ".codex-plugin\plugin.json"
    $bundledBrowserClient = Join-Path $bundledBrowser "scripts\browser-client.mjs"
    $bundledNodeRepl = Join-Path $installRoot "app\resources\cua_node\bin\node_repl.exe"

    foreach ($requiredPath in @($bundledManifest, $bundledBrowserManifest, $bundledBrowserClient, $bundledNodeRepl)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "Required bundled Codex file is missing: $requiredPath"
        }
    }

    $browserPlugin = Get-Content -Raw -LiteralPath $bundledBrowserManifest -Encoding UTF8 | ConvertFrom-Json
    $targetVersion = [string]$browserPlugin.version
    if ([string]::IsNullOrWhiteSpace($targetVersion)) {
        throw "Bundled Browser manifest has no version."
    }

    $cacheRoot = Join-Path $codexHome "plugins\cache\openai-bundled\browser"
    $targetCache = Join-Path $cacheRoot $targetVersion
    $userMarketplace = Join-Path $codexHome ".tmp\bundled-marketplaces\openai-bundled"
    $userMarketplaceManifest = Join-Path $userMarketplace ".agents\plugins\marketplace.json"
    $configPath = Join-Path $codexHome "config.toml"
    $backupRoot = Join-Path $codexHome "browser-repair-backups"

    return [pscustomobject]@{
        CodexHome = $codexHome
        DesktopVersion = [string]$appPackage.Version
        InstallRoot = $installRoot
        BundledMarketplace = $bundledMarketplace
        BundledMarketplaceManifest = $bundledManifest
        BundledBrowser = $bundledBrowser
        BundledBrowserManifest = $bundledBrowserManifest
        BundledBrowserClient = $bundledBrowserClient
        BundledNodeRepl = $bundledNodeRepl
        TargetVersion = $targetVersion
        CacheRoot = $cacheRoot
        TargetCache = $targetCache
        UserMarketplace = $userMarketplace
        UserMarketplaceManifest = $userMarketplaceManifest
        ConfigPath = $configPath
        BackupRoot = $backupRoot
    }
}

function Get-MarketplacePluginVersions {
    param([string]$ManifestPath)

    $result = @{}
    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        return $result
    }

    $marketplace = Get-Content -Raw -LiteralPath $ManifestPath -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in @($marketplace.plugins)) {
        $result[[string]$entry.name] = [string]$entry.source.path
    }
    return $result
}

function Get-CachedBrowserVersions {
    param([string]$CacheRoot)

    if (-not (Test-Path -LiteralPath $CacheRoot)) {
        return @()
    }
    return @(Get-ChildItem -LiteralPath $CacheRoot -Directory -ErrorAction Stop | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName "skills\control-in-app-browser\SKILL.md")
    } | Sort-Object Name | ForEach-Object { $_.Name })
}

function Get-ExtractedNodeReplMatches {
    param([string]$BundledNodeRepl)

    $bundledHash = (Get-FileHash -LiteralPath $BundledNodeRepl -Algorithm SHA256).Hash
    $runtimeRoot = Join-Path $env:LOCALAPPDATA "OpenAI\Codex\runtimes\cua_node"
    $matches = @()
    if (Test-Path -LiteralPath $runtimeRoot) {
        foreach ($file in @(Get-ChildItem -LiteralPath $runtimeRoot -Recurse -Filter "node_repl.exe" -File -ErrorAction SilentlyContinue)) {
            $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
            $matches += [pscustomobject]@{
                Path = $file.FullName
                Hash = $hash
                MatchesBundled = ($hash -eq $bundledHash)
            }
        }
    }
    return $matches
}

function Invoke-Preflight {
    param([switch]$DetailedProcessList)

    Write-Step -Current 1 -Total 4 -Name "VERSION_AND_LAYOUT_CHECK"
    $layout = Get-CodexLayout
    Write-RepairLog -Level "OK" -Message ("Codex Desktop version: {0}" -f $layout.DesktopVersion)
    Write-RepairLog -Level "OK" -Message ("Bundled Browser target: {0}" -f $layout.TargetVersion)

    $cachedVersions = @(Get-CachedBrowserVersions -CacheRoot $layout.CacheRoot)
    if ($cachedVersions.Count -eq 0) {
        Write-RepairLog -Level "WARN" -Message "No cached Browser versions were found."
    } else {
        Write-RepairLog -Level "INFO" -Message ("Cached Browser versions: {0}" -f ($cachedVersions -join ", "))
    }

    $targetCacheMatches = $false
    if (Test-Path -LiteralPath (Join-Path $layout.TargetCache "scripts\browser-client.mjs")) {
        $sourceHash = (Get-FileHash -LiteralPath $layout.BundledBrowserClient -Algorithm SHA256).Hash
        $cacheHash = (Get-FileHash -LiteralPath (Join-Path $layout.TargetCache "scripts\browser-client.mjs") -Algorithm SHA256).Hash
        $targetCacheMatches = ($sourceHash -eq $cacheHash)
    }
    if ($targetCacheMatches) {
        Write-RepairLog -Level "OK" -Message "Target Browser cache exists and matches the desktop bundle."
    } else {
        Write-RepairLog -Level "WARN" -Message "Target Browser cache is missing or does not match the desktop bundle."
    }

    Write-Step -Current 2 -Total 4 -Name "MARKETPLACE_CHECK"
    $userPlugins = Get-MarketplacePluginVersions -ManifestPath $layout.UserMarketplaceManifest
    $bundlePlugins = Get-MarketplacePluginVersions -ManifestPath $layout.BundledMarketplaceManifest
    Write-RepairLog -Level "INFO" -Message ("Bundled marketplace plugins: {0}" -f ((@($bundlePlugins.Keys) | Sort-Object) -join ", "))
    Write-RepairLog -Level "INFO" -Message ("User marketplace plugins: {0}" -f ((@($userPlugins.Keys) | Sort-Object) -join ", "))
    $marketplaceHasBrowser = $userPlugins.ContainsKey("browser")
    if ($marketplaceHasBrowser) {
        Write-RepairLog -Level "OK" -Message "User marketplace snapshot contains Browser."
    } else {
        Write-RepairLog -Level "WARN" -Message "User marketplace snapshot does not contain Browser."
    }

    Write-Step -Current 3 -Total 4 -Name "BROWSER_RUNTIME_CHECK"
    $runtimeMatches = @(Get-ExtractedNodeReplMatches -BundledNodeRepl $layout.BundledNodeRepl)
    if (@($runtimeMatches | Where-Object { $_.MatchesBundled }).Count -gt 0) {
        Write-RepairLog -Level "OK" -Message "At least one extracted Browser runtime matches the desktop bundle."
    } else {
        Write-RepairLog -Level "WARN" -Message "No extracted Browser runtime matches the desktop bundle."
    }
    foreach ($runtime in $runtimeMatches) {
        Write-RepairLog -Level "INFO" -Message ("Runtime MatchesBundled={0} Path={1}" -f $runtime.MatchesBundled, $runtime.Path)
    }

    Write-Step -Current 4 -Total 4 -Name "CODEX_PROCESS_CHECK"
    $processes = @(Get-CodexProcessInventory)
    if ($DetailedProcessList -or $processes.Count -gt 0) {
        Write-CodexProcessInventory -Processes $processes
    }
    $insideCodex = Test-RunningInsideCodex
    if ($insideCodex) {
        Write-RepairLog -Level "WARN" -Message "This PowerShell process is running under a Codex process tree. Repair mode must be started from an independent PowerShell window."
    } else {
        Write-RepairLog -Level "OK" -Message "This PowerShell process is independent from Codex."
    }

    $needsRepair = (-not $targetCacheMatches) -or (-not $marketplaceHasBrowser)
    if ($needsRepair) {
        Write-RepairLog -Level "WARN" -Message "PREFLIGHT_RESULT=REPAIR_RECOMMENDED"
    } else {
        Write-RepairLog -Level "OK" -Message "PREFLIGHT_RESULT=FILES_SYNCHRONIZED"
    }

    return [pscustomobject]@{
        Layout = $layout
        NeedsRepair = $needsRepair
        TargetCacheMatches = $targetCacheMatches
        MarketplaceHasBrowser = $marketplaceHasBrowser
        RunningInsideCodex = $insideCodex
        CodexProcessCount = $processes.Count
    }
}

function Set-ConfigMarketplaceSource {
    param(
        [string]$ConfigPath,
        [string]$MarketplacePath
    )

    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        Write-RepairLog -Level "WARN" -Message "config.toml does not exist; marketplace source was not changed."
        return $false
    }

    $text = [System.IO.File]::ReadAllText($ConfigPath, [System.Text.Encoding]::UTF8)
    $sectionPattern = '(?ms)(^\[marketplaces\.openai-bundled\]\s*$)(.*?)(?=^\[|\z)'
    $match = [regex]::Match($text, $sectionPattern)
    if (-not $match.Success) {
        Write-RepairLog -Level "WARN" -Message "The openai-bundled marketplace section was not found in config.toml."
        return $false
    }

    $body = $match.Groups[2].Value
    $normalized = "\\?\" + [System.IO.Path]::GetFullPath($MarketplacePath)
    $sourceLine = "source = '" + $normalized + "'"
    if ($body -match '(?m)^source\s*=.*$') {
        $newBody = [regex]::Replace($body, '(?m)^source\s*=.*$', $sourceLine, 1)
    } else {
        $newBody = $body + [Environment]::NewLine + $sourceLine + [Environment]::NewLine
    }

    $replacement = $match.Groups[1].Value + $newBody
    $newText = $text.Substring(0, $match.Index) + $replacement + $text.Substring($match.Index + $match.Length)
    [System.IO.File]::WriteAllText($ConfigPath, $newText, $script:Utf8NoBom)
    Write-RepairLog -Level "OK" -Message "Updated openai-bundled marketplace source in config.toml."
    return $true
}

function Copy-DirectoryExact {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Copy source does not exist: $Source"
    }
    if (Test-Path -LiteralPath $Destination) {
        throw "Copy destination already exists: $Destination"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Test-StagedBrowser {
    param(
        [string]$StagedBrowser,
        [object]$Layout
    )

    $manifestPath = Join-Path $StagedBrowser ".codex-plugin\plugin.json"
    $clientPath = Join-Path $StagedBrowser "scripts\browser-client.mjs"
    if (-not (Test-Path -LiteralPath $manifestPath) -or -not (Test-Path -LiteralPath $clientPath)) {
        throw "Staged Browser is incomplete: $StagedBrowser"
    }

    $manifest = Get-Content -Raw -LiteralPath $manifestPath -Encoding UTF8 | ConvertFrom-Json
    if ([string]$manifest.version -ne $Layout.TargetVersion) {
        throw "Staged Browser version mismatch. Expected=$($Layout.TargetVersion) Actual=$($manifest.version)"
    }

    $expectedHash = (Get-FileHash -LiteralPath $Layout.BundledBrowserClient -Algorithm SHA256).Hash
    $actualHash = (Get-FileHash -LiteralPath $clientPath -Algorithm SHA256).Hash
    if ($expectedHash -ne $actualHash) {
        throw "Staged browser-client.mjs hash mismatch."
    }
}

function Write-RepairManifest {
    param(
        [string]$Path,
        [hashtable]$Data
    )

    $json = $Data | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $script:Utf8NoBom)
}

function Restore-FromBackupCore {
    param(
        [string]$SelectedBackup,
        [switch]$Automatic
    )

    $manifestPath = Join-Path $SelectedBackup "repair-manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Repair manifest not found in backup: $SelectedBackup"
    }
    $manifest = Get-Content -Raw -LiteralPath $manifestPath -Encoding UTF8 | ConvertFrom-Json

    $codexHome = [string]$manifest.CodexHome
    $userMarketplace = [string]$manifest.UserMarketplace
    $targetCache = [string]$manifest.TargetCache
    Assert-PathUnderRoot -Path $SelectedBackup -Root $codexHome -Label "Backup path"
    Assert-PathUnderRoot -Path $userMarketplace -Root $codexHome -Label "Marketplace path"
    Assert-PathUnderRoot -Path $targetCache -Root $codexHome -Label "Target cache path"

    $rollbackStamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $marketplaceDisplaced = Join-Path $SelectedBackup "marketplace-displaced"
    $marketplaceWasDisplaced = Test-Path -LiteralPath $marketplaceDisplaced
    $shouldQuarantineMarketplace = (-not [bool]$manifest.HadUserMarketplace) -or $marketplaceWasDisplaced
    if ($shouldQuarantineMarketplace -and (Test-Path -LiteralPath $userMarketplace)) {
        $quarantine = Join-Path $SelectedBackup ("rollback-quarantine-marketplace-{0}" -f $rollbackStamp)
        Move-Item -LiteralPath $userMarketplace -Destination $quarantine
        Write-RepairLog -Level "INFO" -Message "Moved repaired marketplace to rollback quarantine."
    }

    if ([bool]$manifest.HadUserMarketplace -and $marketplaceWasDisplaced) {
        Move-Item -LiteralPath $marketplaceDisplaced -Destination $userMarketplace
        Write-RepairLog -Level "OK" -Message "Restored the original user marketplace."
    } elseif ([bool]$manifest.HadUserMarketplace -and (Test-Path -LiteralPath $userMarketplace)) {
        Write-RepairLog -Level "INFO" -Message "Original user marketplace was never displaced and remains in place."
    }

    $targetCacheDisplaced = Join-Path $SelectedBackup "target-cache-displaced"
    $targetCacheWasDisplaced = Test-Path -LiteralPath $targetCacheDisplaced
    $shouldQuarantineTargetCache = (-not [bool]$manifest.HadTargetCache) -or $targetCacheWasDisplaced
    if ($shouldQuarantineTargetCache -and (Test-Path -LiteralPath $targetCache)) {
        $cacheQuarantine = Join-Path $SelectedBackup ("rollback-quarantine-target-cache-{0}" -f $rollbackStamp)
        Move-Item -LiteralPath $targetCache -Destination $cacheQuarantine
        Write-RepairLog -Level "INFO" -Message "Moved repaired target cache to rollback quarantine."
    }

    if ([bool]$manifest.HadTargetCache -and $targetCacheWasDisplaced) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetCache) | Out-Null
        Move-Item -LiteralPath $targetCacheDisplaced -Destination $targetCache
        Write-RepairLog -Level "OK" -Message "Restored the original target cache."
    } elseif ([bool]$manifest.HadTargetCache -and (Test-Path -LiteralPath $targetCache)) {
        Write-RepairLog -Level "INFO" -Message "Original target cache was never displaced and remains in place."
    }

    $configBackup = Join-Path $SelectedBackup "config.toml.original"
    if ([bool]$manifest.HadConfig -and (Test-Path -LiteralPath $configBackup)) {
        Copy-Item -LiteralPath $configBackup -Destination ([string]$manifest.ConfigPath) -Force
        Write-RepairLog -Level "OK" -Message "Restored config.toml."
    }

    $markerName = if ($Automatic) { "AUTOMATIC_ROLLBACK_COMPLETE" } else { "ROLLBACK_COMPLETE" }
    [System.IO.File]::WriteAllText((Join-Path $SelectedBackup $markerName), (Get-Date).ToString("o"), $script:Utf8NoBom)
    Write-RepairLog -Level "OK" -Message $markerName
}

function Invoke-Repair {
    if (-not $ConfirmRepair) {
        throw "Repair mode requires -ConfirmRepair. Run Preflight first, then use: .\scripts\repair-codex-browser.ps1 -Mode Repair -ConfirmRepair"
    }
    if (Test-RunningInsideCodex) {
        throw "Repair mode is running under the Codex process tree. Open an independent PowerShell window and start the script there."
    }

    Enter-RepairLock
    $backupDirectory = ""
    $commitStarted = $false
    try {
        Write-Step -Current 1 -Total 8 -Name "PREFLIGHT"
        $preflight = Invoke-Preflight
        $layout = $preflight.Layout

        Write-Step -Current 2 -Total 8 -Name "WAITING_FOR_CODEX_EXIT"
        Wait-ForCodexExit -TimeoutSeconds $WaitTimeoutSeconds -RequiredStableSeconds $StableSeconds

        Write-Step -Current 3 -Total 8 -Name "CREATE_BACKUP"
        New-Item -ItemType Directory -Force -Path $layout.BackupRoot | Out-Null
        $backupDirectory = Join-Path $layout.BackupRoot $script:RunStamp
        if (Test-Path -LiteralPath $backupDirectory) {
            throw "Backup directory already exists: $backupDirectory"
        }
        New-Item -ItemType Directory -Path $backupDirectory | Out-Null

        $hadMarketplace = Test-Path -LiteralPath $layout.UserMarketplace
        $hadTargetCache = Test-Path -LiteralPath $layout.TargetCache
        $hadConfig = Test-Path -LiteralPath $layout.ConfigPath
        if ($hadConfig) {
            Copy-Item -LiteralPath $layout.ConfigPath -Destination (Join-Path $backupDirectory "config.toml.original") -Force
        }

        $manifestData = @{
            SchemaVersion = 1
            CreatedAt = (Get-Date).ToString("o")
            DesktopVersion = $layout.DesktopVersion
            TargetBrowserVersion = $layout.TargetVersion
            CodexHome = $layout.CodexHome
            UserMarketplace = $layout.UserMarketplace
            TargetCache = $layout.TargetCache
            ConfigPath = $layout.ConfigPath
            HadUserMarketplace = $hadMarketplace
            HadTargetCache = $hadTargetCache
            HadConfig = $hadConfig
            RepairConfigSource = [bool]$RepairConfigSource
            Status = "BACKUP_CREATED"
        }
        $repairManifestPath = Join-Path $backupDirectory "repair-manifest.json"
        Write-RepairManifest -Path $repairManifestPath -Data $manifestData
        Write-RepairLog -Level "OK" -Message "Backup directory: $backupDirectory"

        Write-Step -Current 4 -Total 8 -Name "STAGE_AND_VERIFY"
        $stageRoot = Join-Path $layout.CodexHome (".tmp\codex-browser-repair-stage-{0}" -f $script:RunStamp)
        $stageMarketplace = Join-Path $stageRoot "openai-bundled"
        $stageCache = Join-Path $stageRoot "browser-cache"
        Assert-PathUnderRoot -Path $stageRoot -Root $layout.CodexHome -Label "Stage path"
        Copy-DirectoryExact -Source $layout.BundledMarketplace -Destination $stageMarketplace
        Copy-DirectoryExact -Source $layout.BundledBrowser -Destination $stageCache
        Test-StagedBrowser -StagedBrowser $stageCache -Layout $layout
        $stagePlugins = Get-MarketplacePluginVersions -ManifestPath (Join-Path $stageMarketplace ".agents\plugins\marketplace.json")
        if (-not $stagePlugins.ContainsKey("browser")) {
            throw "Staged marketplace does not contain Browser."
        }
        Write-RepairLog -Level "OK" -Message "Staged Browser and marketplace hashes verified."

        Write-Step -Current 5 -Total 8 -Name "COMMIT_MARKETPLACE"
        $commitStarted = $true
        $manifestData.Status = "COMMIT_STARTED"
        Write-RepairManifest -Path $repairManifestPath -Data $manifestData
        if ($hadMarketplace) {
            Move-Item -LiteralPath $layout.UserMarketplace -Destination (Join-Path $backupDirectory "marketplace-displaced")
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $layout.UserMarketplace) | Out-Null
        Move-Item -LiteralPath $stageMarketplace -Destination $layout.UserMarketplace
        Write-RepairLog -Level "OK" -Message "Installed the complete bundled marketplace snapshot."

        Write-Step -Current 6 -Total 8 -Name "COMMIT_BROWSER_CACHE"
        New-Item -ItemType Directory -Force -Path $layout.CacheRoot | Out-Null
        if ($hadTargetCache) {
            Move-Item -LiteralPath $layout.TargetCache -Destination (Join-Path $backupDirectory "target-cache-displaced")
        }
        Move-Item -LiteralPath $stageCache -Destination $layout.TargetCache
        if ($RepairConfigSource) {
            [void](Set-ConfigMarketplaceSource -ConfigPath $layout.ConfigPath -MarketplacePath $layout.UserMarketplace)
        }
        if (Test-Path -LiteralPath $stageRoot) {
            Remove-Item -LiteralPath $stageRoot -Recurse -Force
        }
        Write-RepairLog -Level "OK" -Message ("Installed Browser cache version {0}." -f $layout.TargetVersion)

        Write-Step -Current 7 -Total 8 -Name "OFFLINE_VERIFICATION"
        Test-StagedBrowser -StagedBrowser $layout.TargetCache -Layout $layout
        $installedPlugins = Get-MarketplacePluginVersions -ManifestPath $layout.UserMarketplaceManifest
        if (-not $installedPlugins.ContainsKey("browser")) {
            throw "Offline verification failed: installed marketplace has no Browser entry."
        }
        $processesAfterCommit = @(Get-CodexProcessInventory)
        if ($processesAfterCommit.Count -gt 0) {
            Write-CodexProcessInventory -Processes $processesAfterCommit
            throw "A Codex process started during the repair. Offline state may have been modified concurrently."
        }
        $manifestData.Status = "OFFLINE_REPAIR_OK"
        $manifestData.CompletedAt = (Get-Date).ToString("o")
        Write-RepairManifest -Path $repairManifestPath -Data $manifestData
        [System.IO.File]::WriteAllText((Join-Path $backupDirectory "OFFLINE_REPAIR_OK"), (Get-Date).ToString("o"), $script:Utf8NoBom)
        Write-RepairLog -Level "OK" -Message "OFFLINE_REPAIR_OK"

        Write-Step -Current 8 -Total 8 -Name "COMPLETE"
        Write-RepairLog -Level "OK" -Message "SAFE_TO_REOPEN_CODEX"
        Write-RepairLog -Level "INFO" -Message "Open Codex Desktop, create a new conversation, and ask it to use Browser. Live Browser control is the final acceptance test."
        Write-RepairLog -Level "INFO" -Message "Rollback command (run with Codex closed):"
        Write-RepairLog -Level "INFO" -Message ("  .\scripts\repair-codex-browser.ps1 -Mode Rollback -BackupPath `"{0}`" -ConfirmRollback" -f $backupDirectory)
    } catch {
        Write-RepairLog -Level "ERROR" -Message $_.Exception.Message
        if ($commitStarted -and -not [string]::IsNullOrWhiteSpace($backupDirectory)) {
            Write-RepairLog -Level "WARN" -Message "Commit had started. Attempting automatic rollback..."
            try {
                Restore-FromBackupCore -SelectedBackup $backupDirectory -Automatic
            } catch {
                Write-RepairLog -Level "ERROR" -Message ("Automatic rollback failed: {0}" -f $_.Exception.Message)
                Write-RepairLog -Level "ERROR" -Message ("Do not reopen Codex until the backup is inspected: {0}" -f $backupDirectory)
            }
        }
        throw
    } finally {
        Exit-RepairLock
    }
}

function Invoke-Rollback {
    if (-not $ConfirmRollback) {
        throw "Rollback mode requires -ConfirmRollback."
    }
    if (Test-RunningInsideCodex) {
        throw "Rollback mode is running under the Codex process tree. Open an independent PowerShell window and start it there."
    }

    Enter-RepairLock
    try {
        $layout = Get-CodexLayout
        $selectedBackup = $BackupPath
        if ([string]::IsNullOrWhiteSpace($selectedBackup)) {
            if (-not (Test-Path -LiteralPath $layout.BackupRoot)) {
                throw "No Browser repair backup directory exists."
            }
            $candidate = Get-ChildItem -LiteralPath $layout.BackupRoot -Directory | Sort-Object Name -Descending | Where-Object {
                Test-Path -LiteralPath (Join-Path $_.FullName "repair-manifest.json")
            } | Select-Object -First 1
            if ($null -eq $candidate) {
                throw "No usable Browser repair backup was found."
            }
            $selectedBackup = $candidate.FullName
        }
        $selectedBackup = [System.IO.Path]::GetFullPath($selectedBackup)
        Assert-PathUnderRoot -Path $selectedBackup -Root $layout.BackupRoot -Label "Rollback backup"
        Write-RepairLog -Level "INFO" -Message "Selected rollback backup: $selectedBackup"

        Wait-ForCodexExit -TimeoutSeconds $WaitTimeoutSeconds -RequiredStableSeconds $StableSeconds
        Restore-FromBackupCore -SelectedBackup $selectedBackup
        Write-RepairLog -Level "OK" -Message "SAFE_TO_REOPEN_CODEX"
    } finally {
        Exit-RepairLock
    }
}

try {
    Write-RepairLog -Level "INFO" -Message "Codex Browser controlled repair"
    Write-RepairLog -Level "INFO" -Message ("Mode={0} PID={1} PowerShell={2}" -f $Mode, $PID, $PSVersionTable.PSVersion)
    Write-RepairLog -Level "INFO" -Message "Log file: $script:LogPath"

    switch ($Mode) {
        "ProcessScan" {
            $processes = @(Get-CodexProcessInventory)
            Write-CodexProcessInventory -Processes $processes
            if (Test-RunningInsideCodex) {
                Write-RepairLog -Level "WARN" -Message "RUN_CONTEXT=INSIDE_CODEX_PROCESS_TREE"
            } else {
                Write-RepairLog -Level "OK" -Message "RUN_CONTEXT=INDEPENDENT_POWERSHELL"
            }
        }
        "Preflight" {
            [void](Invoke-Preflight -DetailedProcessList)
        }
        "Repair" {
            Invoke-Repair
        }
        "Rollback" {
            Invoke-Rollback
        }
    }
} catch {
    Write-RepairLog -Level "ERROR" -Message $_.Exception.Message
    Write-RepairLog -Level "ERROR" -Message ("FAILED. Review log: {0}" -f $script:LogPath)
    exit 1
} finally {
    Exit-RepairLock
}

Write-RepairLog -Level "OK" -Message ("Finished. Log: {0}" -f $script:LogPath)
exit 0
