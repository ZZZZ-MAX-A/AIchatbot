<#
.SYNOPSIS
    Controlled switch from the current Codex Desktop AppX registration to a
    verified staged build, with a matching personal Browser plugin.

.DESCRIPTION
    ProcessScan and Preflight are read-only. Upgrade and Rollback must be run
    from an independent PowerShell window. The script never terminates Codex;
    it waits until every detected Codex process and descendant has exited and
    the shutdown state has remained stable for the requested interval.

.EXAMPLE
    .\scripts\switch-codex-staged-build.ps1 -Mode ProcessScan

.EXAMPLE
    .\scripts\switch-codex-staged-build.ps1 -Mode Preflight

.EXAMPLE
    .\scripts\switch-codex-staged-build.ps1 -Mode Upgrade -ConfirmUpgrade

.EXAMPLE
    .\scripts\switch-codex-staged-build.ps1 -Mode Rollback -ConfirmRollback
#>
[CmdletBinding()]
param(
    [ValidateSet("ProcessScan", "Preflight", "Upgrade", "Rollback")]
    [string]$Mode = "Preflight",

    [int]$WaitTimeoutSeconds = 900,

    [ValidateRange(3, 30)]
    [int]$StableSeconds = 5,

    [string]$BackupPath = "",

    [switch]$ConfirmUpgrade,

    [switch]$ConfirmRollback
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script:TargetPackageRoot = "C:\Program Files\WindowsApps\OpenAI.Codex_26.715.8383.0_x64__2p2nqsd0c76g0"
$script:TargetDesktopVersion = "26.715.8383.0"
$script:TargetBrowserVersionPrefix = "26.715.61943"
$script:TargetBrowserClientHash = "0B03C76C1D0F3D4C81F89F58FF210AE6709FD1204D2C5A4FDFFA0A7BDB961B96"
$script:TargetCoreHash = "96B09EF15C5D6B5D36A905D2318D86690526092CB3552BF7B20BF126B45F819F"
$script:TargetManifestHash = "86A4079C3AF46898B47A5827A72930C5ADA200F6B7E2CE99F37D85FFD0187C5F"
$script:TargetSignatureHash = "7990EF6E8E9E5FC45514667BD0122FD122E3BF6EFD1A6342472F0FC6B18600BF"
$script:StagePluginRoot = Join-Path $script:RepoRoot "tmp\personal-plugin-stage-8383\browser-pinned"
$script:BackupRoot = Join-Path $script:RepoRoot "backups\codex-staged-build-switch"
$script:LogRoot = Join-Path $script:RepoRoot "logs"
$script:RunStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:LockStream = $null

try {
    New-Item -ItemType Directory -Force -Path $script:LogRoot | Out-Null
} catch {
    $script:LogRoot = Join-Path ([System.IO.Path]::GetTempPath()) "codex-staged-build-switch-logs"
    New-Item -ItemType Directory -Force -Path $script:LogRoot | Out-Null
}
$script:LogPath = Join-Path $script:LogRoot ("codex-staged-build-{0}-{1}.log" -f $Mode.ToLowerInvariant(), $script:RunStamp)

function Write-SwitchLog {
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

function Get-FullPath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-PathUnderRoot {
    param(
        [string]$Path,
        [string]$Root,
        [string]$Label
    )

    $fullPath = (Get-FullPath -Path $Path).TrimEnd("\")
    $fullRoot = (Get-FullPath -Path $Root).TrimEnd("\")
    if ($fullPath -eq $fullRoot) { return }
    if (-not $fullPath.StartsWith($fullRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label escapes its allowed root: $fullPath"
    }
}

function Get-AllProcessInfo {
    return @(Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object {
        [pscustomobject]@{
            Name = [string]$_.Name
            ProcessId = [int]$_.ProcessId
            ParentProcessId = [int]$_.ParentProcessId
            ExecutablePath = [string]$_.ExecutablePath
            CommandLine = [string]$_.CommandLine
            MatchReason = ""
        }
    })
}

function Get-NormalizedProcessText {
    param([object]$ProcessInfo)
    return ((@($ProcessInfo.Name, $ProcessInfo.ExecutablePath, $ProcessInfo.CommandLine) -join " ").Replace("/", "\")).ToLowerInvariant()
}

function Get-CodexSignatureReason {
    param([object]$ProcessInfo)

    $name = ([string]$ProcessInfo.Name).ToLowerInvariant()
    $text = Get-NormalizedProcessText -ProcessInfo $ProcessInfo
    $exactNames = @(
        "codex.exe",
        "codex-code-mode-host.exe",
        "codex-command-runner.exe",
        "codex-computer-use.exe",
        "node_repl.exe",
        "openai.codex.exe",
        "codex-desktop.exe"
    )
    if ($exactNames -contains $name) {
        return "Codex executable"
    }

    $markers = @(
        "\windowsapps\openai.codex_",
        "\packages\openai.codex_",
        "\appdata\roaming\npm\node_modules\@openai\codex\",
        "\appdata\local\openai\codex\runtimes\",
        "\localcache\roaming\codex\web\codex\",
        "\localcache\local\codex\"
    )
    foreach ($marker in $markers) {
        if ($text.Contains($marker)) {
            return "Codex path marker: $marker"
        }
    }

    if ($name -eq "node.exe" -and $text -match "@openai\\codex\\bin\\codex\.js") {
        return "Codex npm launcher"
    }
    if ($name -eq "msedgewebview2.exe" -and $text.Contains("openai.codex")) {
        return "Codex WebView"
    }
    return ""
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
                $process.MatchReason = "Descendant of PID $($process.ParentProcessId)"
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
    foreach ($process in $all) { $byId[$process.ProcessId] = $process }
    $result = @()
    $currentId = $PID
    $visited = @{}
    while ($byId.ContainsKey($currentId) -and -not $visited.ContainsKey($currentId)) {
        $visited[$currentId] = $true
        $current = $byId[$currentId]
        $result += $current
        if ($current.ParentProcessId -le 0) { break }
        $currentId = $current.ParentProcessId
    }
    return $result
}

function Test-RunningInsideCodex {
    foreach ($process in @(Get-CurrentProcessAncestors)) {
        if ($process.ProcessId -eq $PID) { continue }
        if (-not [string]::IsNullOrWhiteSpace((Get-CodexSignatureReason -ProcessInfo $process))) {
            return $true
        }
    }
    return $false
}

function Write-CodexProcessInventory {
    param([object[]]$Processes)

    if ($Processes.Count -eq 0) {
        Write-SwitchLog -Level "OK" -Message "NO_CODEX_PROCESS_DETECTED"
        return
    }
    Write-SwitchLog -Level "WARN" -Message ("CODEX_PROCESS_COUNT={0}" -f $Processes.Count)
    foreach ($process in $Processes) {
        Write-SwitchLog -Level "WARN" -Message (
            "PID={0} PPID={1} NAME={2} REASON={3}" -f $process.ProcessId, $process.ParentProcessId, $process.Name, $process.MatchReason
        )
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
            if ($signature -ne $lastSignature) { Write-CodexProcessInventory -Processes $processes }
            $stableSince = $null
            $lastSignature = $signature
        } else {
            if ($null -eq $stableSince) {
                $stableSince = Get-Date
                Write-SwitchLog -Level "INFO" -Message ("VERIFYING_STABLE_EXIT_{0}_SECONDS" -f $RequiredStableSeconds)
            }
            if (((Get-Date) - $stableSince).TotalSeconds -ge $RequiredStableSeconds) {
                Write-SwitchLog -Level "OK" -Message "CODEX_EXIT_CONFIRMED"
                return
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out while waiting for every Codex process to exit."
}

function Enter-SwitchLock {
    New-Item -ItemType Directory -Force -Path $script:BackupRoot | Out-Null
    $lockPath = Join-Path $script:BackupRoot "switch.lock"
    try {
        $script:LockStream = New-Object System.IO.FileStream($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    } catch {
        throw "Another staged-build switch or rollback is already running."
    }
}

function Exit-SwitchLock {
    if ($null -ne $script:LockStream) {
        $script:LockStream.Dispose()
        $script:LockStream = $null
    }
}

function Get-Sha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing required file: $Path" }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Assert-Hash {
    param(
        [string]$Path,
        [string]$Expected,
        [string]$Label
    )
    $actual = Get-Sha256 -Path $Path
    if ($actual -ne $Expected) { throw "$Label hash mismatch. Expected $Expected; got $actual" }
}

function Get-PluginPython {
    $candidates = @(
        (Join-Path $script:RepoRoot ".venv\Scripts\python.exe"),
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    throw "No usable Python executable was found for plugin validation."
}

function Get-CodexCommand {
    foreach ($name in @("codex.cmd", "codex.exe", "codex")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    throw "The Codex CLI command was not found in PATH."
}

function Invoke-PluginValidation {
    param([string]$PluginRoot)

    $validator = Join-Path $env:USERPROFILE ".codex\skills\.system\plugin-creator\scripts\validate_plugin.py"
    if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) { throw "Plugin validator is missing: $validator" }
    $python = Get-PluginPython
    $output = & $python $validator $PluginRoot 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Plugin validation failed: $output" }
}

function Get-PersonalMarketplaceName {
    $reader = Join-Path $env:USERPROFILE ".codex\skills\.system\plugin-creator\scripts\read_marketplace_name.py"
    if (-not (Test-Path -LiteralPath $reader -PathType Leaf)) { throw "Marketplace-name helper is missing: $reader" }
    $python = Get-PluginPython
    $output = (& $python $reader 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($output)) {
        throw "Unable to read the personal marketplace name: $output"
    }
    return $output
}

function Invoke-RobocopyExact {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { throw "$Label source is missing: $Source" }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy.exe $Source $Destination /MIR /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NP /NFL /NDL /NJH /NJS | Out-Null
    $code = $LASTEXITCODE
    if ($code -gt 7) { throw "$Label copy failed with robocopy exit code $code" }
}

function Invoke-RobocopyBackup {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { return $false }
    if (Test-Path -LiteralPath $Destination) { throw "$Label backup destination already exists: $Destination" }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy.exe $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NP /NFL /NDL /NJH /NJS | Out-Null
    $code = $LASTEXITCODE
    if ($code -gt 7) { throw "$Label backup failed with robocopy exit code $code" }
    return $true
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Data
    )
    [System.IO.File]::WriteAllText($Path, ($Data | ConvertTo-Json -Depth 8), $script:Utf8NoBom)
}

function Get-StageLayout {
    $targetManifest = Join-Path $script:TargetPackageRoot "AppxManifest.xml"
    $targetSignature = Join-Path $script:TargetPackageRoot "AppxSignature.p7x"
    $targetCore = Join-Path $script:TargetPackageRoot "app\resources\codex.exe"
    $targetBundledBrowser = Join-Path $script:TargetPackageRoot "app\resources\plugins\openai-bundled\plugins\browser\scripts\browser-client.mjs"
    $stageManifest = Join-Path $script:StagePluginRoot ".codex-plugin\plugin.json"
    $stageBrowser = Join-Path $script:StagePluginRoot "scripts\browser-client.mjs"

    foreach ($path in @($targetManifest, $targetSignature, $targetCore, $targetBundledBrowser, $stageManifest, $stageBrowser)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required staged file is missing: $path" }
    }

    [xml]$appx = Get-Content -Raw -LiteralPath $targetManifest
    if ([string]$appx.Package.Identity.Name -ne "OpenAI.Codex") { throw "Unexpected staged AppX identity name." }
    if ([string]$appx.Package.Identity.Version -ne $script:TargetDesktopVersion) { throw "Unexpected staged AppX version." }
    if ([string]$appx.Package.Identity.Publisher -ne "CN=50BDFD77-8903-4850-9FFE-6E8522F64D5B") { throw "Unexpected staged AppX publisher." }

    Assert-Hash -Path $targetManifest -Expected $script:TargetManifestHash -Label "AppX manifest"
    Assert-Hash -Path $targetSignature -Expected $script:TargetSignatureHash -Label "AppX signature"
    Assert-Hash -Path $targetCore -Expected $script:TargetCoreHash -Label "Codex core"
    Assert-Hash -Path $targetBundledBrowser -Expected $script:TargetBrowserClientHash -Label "Bundled Browser client"
    Assert-Hash -Path $stageBrowser -Expected $script:TargetBrowserClientHash -Label "Personal Browser client"

    $plugin = Get-Content -Raw -LiteralPath $stageManifest | ConvertFrom-Json
    if ([string]$plugin.name -ne "browser-pinned") { throw "Unexpected staged personal plugin name." }
    $pluginVersion = [string]$plugin.version
    if (-not $pluginVersion.StartsWith($script:TargetBrowserVersionPrefix + "+codex.", [System.StringComparison]::Ordinal)) {
        throw "Unexpected staged personal plugin version: $pluginVersion"
    }
    Invoke-PluginValidation -PluginRoot $script:StagePluginRoot

    $marketplacePath = Join-Path $env:USERPROFILE ".agents\plugins\marketplace.json"
    if (-not (Test-Path -LiteralPath $marketplacePath -PathType Leaf)) { throw "Personal marketplace is missing: $marketplacePath" }
    $marketplace = Get-Content -Raw -LiteralPath $marketplacePath | ConvertFrom-Json
    $entry = @($marketplace.plugins | Where-Object { [string]$_.name -eq "browser-pinned" })
    if ($entry.Count -ne 1) { throw "Personal marketplace must contain exactly one browser-pinned entry." }
    if ([string]$entry[0].source.source -ne "local" -or [string]$entry[0].source.path -ne "./plugins/browser-pinned") {
        throw "The personal browser-pinned marketplace source is not the expected local source."
    }

    return [pscustomobject]@{
        TargetManifest = $targetManifest
        TargetCore = $targetCore
        TargetBundledBrowser = $targetBundledBrowser
        StageManifest = $stageManifest
        StageBrowser = $stageBrowser
        PluginVersion = $pluginVersion
        MarketplacePath = $marketplacePath
    }
}

function Invoke-Preflight {
    $stage = Get-StageLayout
    $packages = @(Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction Stop | Sort-Object Version -Descending)
    if ($packages.Count -eq 0) { throw "No Codex Desktop package is registered for the current user." }
    $current = $packages[0]
    $processes = @(Get-CodexProcessInventory)
    Write-CodexProcessInventory -Processes $processes
    if (Test-RunningInsideCodex) {
        Write-SwitchLog -Level "WARN" -Message "RUN_CONTEXT=INSIDE_CODEX_PROCESS_TREE"
    } else {
        Write-SwitchLog -Level "OK" -Message "RUN_CONTEXT=INDEPENDENT_POWERSHELL"
    }
    Write-SwitchLog -Level "INFO" -Message ("CURRENT_DESKTOP_VERSION={0}" -f $current.Version)
    Write-SwitchLog -Level "INFO" -Message ("TARGET_DESKTOP_VERSION={0}" -f $script:TargetDesktopVersion)
    Write-SwitchLog -Level "INFO" -Message ("TARGET_PERSONAL_BROWSER_VERSION={0}" -f $stage.PluginVersion)
    Write-SwitchLog -Level "OK" -Message "STAGED_BUILD_PREFLIGHT_OK"
    return [pscustomobject]@{ Stage = $stage; CurrentPackage = $current }
}

function New-FullBackup {
    param(
        [object]$CurrentPackage,
        [object]$Stage
    )

    New-Item -ItemType Directory -Force -Path $script:BackupRoot | Out-Null
    $backup = Join-Path $script:BackupRoot $script:RunStamp
    Assert-PathUnderRoot -Path $backup -Root $script:BackupRoot -Label "Backup path"
    if (Test-Path -LiteralPath $backup) { throw "Backup path already exists: $backup" }
    New-Item -ItemType Directory -Path $backup | Out-Null

    $codexHome = Join-Path $env:USERPROFILE ".codex"
    $roamingCodex = Join-Path $env:APPDATA "Codex"
    $personalPlugin = Join-Path $env:USERPROFILE "plugins\browser-pinned"
    $personalAgents = Join-Path $env:USERPROFILE ".agents"
    $packageData = Join-Path $env:LOCALAPPDATA "Packages\OpenAI.Codex_2p2nqsd0c76g0"
    $appxBackup = Join-Path $backup "appx-package-original"

    Write-SwitchLog -Level "INFO" -Message "BACKUP_STARTED"
    $hadCodexHome = Invoke-RobocopyBackup -Source $codexHome -Destination (Join-Path $backup "codex-home") -Label "Codex home"
    $hadRoamingCodex = Invoke-RobocopyBackup -Source $roamingCodex -Destination (Join-Path $backup "roaming-codex") -Label "Codex roaming data"
    $hadPersonalPlugin = Invoke-RobocopyBackup -Source $personalPlugin -Destination (Join-Path $backup "personal-plugin-source") -Label "Personal plugin"
    $hadPersonalAgents = Invoke-RobocopyBackup -Source $personalAgents -Destination (Join-Path $backup "personal-agents") -Label "Personal marketplace"
    $hadPackageData = Invoke-RobocopyBackup -Source $packageData -Destination (Join-Path $backup "appx-package-data") -Label "Codex AppX user data"
    $hadOriginalAppx = Invoke-RobocopyBackup -Source ([string]$CurrentPackage.InstallLocation) -Destination $appxBackup -Label "Original Codex AppX"
    if (-not $hadOriginalAppx) { throw "The original Codex AppX package could not be backed up." }

    $oldPluginVersion = ""
    $oldPluginManifest = Join-Path $personalPlugin ".codex-plugin\plugin.json"
    if (Test-Path -LiteralPath $oldPluginManifest -PathType Leaf) {
        $oldPluginVersion = [string]((Get-Content -Raw -LiteralPath $oldPluginManifest | ConvertFrom-Json).version)
    }

    $oldCore = Join-Path ([string]$CurrentPackage.InstallLocation) "app\resources\codex.exe"
    $oldBrowser = Join-Path ([string]$CurrentPackage.InstallLocation) "app\resources\plugins\openai-bundled\plugins\browser\scripts\browser-client.mjs"
    $manifest = [ordered]@{
        CreatedAt = (Get-Date).ToString("o")
        BackupPath = $backup
        OriginalDesktopVersion = [string]$CurrentPackage.Version
        OriginalInstallLocation = [string]$CurrentPackage.InstallLocation
        OriginalCoreHash = Get-Sha256 -Path $oldCore
        OriginalBundledBrowserHash = Get-Sha256 -Path $oldBrowser
        TargetDesktopVersion = $script:TargetDesktopVersion
        TargetPackageRoot = $script:TargetPackageRoot
        TargetPersonalBrowserVersion = [string]$Stage.PluginVersion
        OriginalPersonalBrowserVersion = $oldPluginVersion
        HadCodexHome = [bool]$hadCodexHome
        HadRoamingCodex = [bool]$hadRoamingCodex
        HadPersonalPlugin = [bool]$hadPersonalPlugin
        HadPersonalAgents = [bool]$hadPersonalAgents
        HadPackageData = [bool]$hadPackageData
        HadOriginalAppx = [bool]$hadOriginalAppx
        AppxSwitchCommitted = $false
        PersonalPluginCommitted = $false
    }
    $manifestPath = Join-Path $backup "switch-manifest.json"
    Write-JsonFile -Path $manifestPath -Data $manifest
    Write-SwitchLog -Level "OK" -Message "FULL_BACKUP_OK"
    Write-SwitchLog -Level "INFO" -Message ("BACKUP_PATH={0}" -f $backup)
    return [pscustomobject]@{ Path = $backup; ManifestPath = $manifestPath; Data = $manifest }
}

function Save-BackupManifest {
    param([object]$Backup)
    Write-JsonFile -Path ([string]$Backup.ManifestPath) -Data $Backup.Data
}

function Register-AppxManifest {
    param(
        [string]$ManifestPath,
        [switch]$AllowDowngrade
    )

    if ($AllowDowngrade) {
        Add-AppxPackage -Register $ManifestPath -DisableDevelopmentMode -ForceApplicationShutdown -ForceUpdateFromAnyVersion -ErrorAction Stop
    } else {
        Add-AppxPackage -Register $ManifestPath -DisableDevelopmentMode -ForceApplicationShutdown -ErrorAction Stop
    }
}

function Assert-RegisteredDesktopVersion {
    param([string]$ExpectedVersion)
    $registered = @(Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction Stop | Where-Object { [string]$_.Version -eq $ExpectedVersion })
    if ($registered.Count -eq 0) {
        $actual = @((Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction SilentlyContinue) | ForEach-Object { [string]$_.Version }) -join ","
        throw "Registered Codex Desktop version mismatch. Expected $ExpectedVersion; got $actual"
    }
    return $registered[0]
}

function Install-PersonalBrowser {
    param(
        [string]$SourceRoot,
        [string]$ExpectedVersion,
        [string]$ExpectedBrowserHash
    )

    $personalPluginRoot = Join-Path $env:USERPROFILE "plugins\browser-pinned"
    $pluginsRoot = Join-Path $env:USERPROFILE "plugins"
    Assert-PathUnderRoot -Path $personalPluginRoot -Root $pluginsRoot -Label "Personal plugin destination"
    Invoke-RobocopyExact -Source $SourceRoot -Destination $personalPluginRoot -Label "Personal Browser"
    Invoke-PluginValidation -PluginRoot $personalPluginRoot
    Assert-Hash -Path (Join-Path $personalPluginRoot "scripts\browser-client.mjs") -Expected $ExpectedBrowserHash -Label "Installed personal Browser source"

    $marketplaceName = Get-PersonalMarketplaceName
    $codex = Get-CodexCommand
    $pluginId = "browser-pinned@{0}" -f $marketplaceName
    $output = & $codex plugin add $pluginId --json 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "codex plugin add failed: $output" }

    $cacheRoot = Join-Path $env:USERPROFILE ".codex\plugins\cache\$marketplaceName\browser-pinned"
    if (-not (Test-Path -LiteralPath $cacheRoot -PathType Container)) { throw "Personal Browser cache root is missing: $cacheRoot" }
    $match = $null
    foreach ($directory in @(Get-ChildItem -LiteralPath $cacheRoot -Directory | Sort-Object LastWriteTime -Descending)) {
        $manifestPath = Join-Path $directory.FullName ".codex-plugin\plugin.json"
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { continue }
        $candidateVersion = [string]((Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json).version)
        if ($candidateVersion -eq $ExpectedVersion) { $match = $directory; break }
    }
    if ($null -eq $match) { throw "No installed personal Browser cache matches version $ExpectedVersion" }
    Assert-Hash -Path (Join-Path $match.FullName "scripts\browser-client.mjs") -Expected $ExpectedBrowserHash -Label "Installed personal Browser cache"
    return $match.FullName
}

function Invoke-Upgrade {
    if (-not $ConfirmUpgrade) { throw "Upgrade mode requires -ConfirmUpgrade." }
    if (Test-RunningInsideCodex) { throw "Upgrade must be started from an independent PowerShell window." }

    Enter-SwitchLock
    $backup = $null
    try {
        $preflight = Invoke-Preflight
        Wait-ForCodexExit -TimeoutSeconds $WaitTimeoutSeconds -RequiredStableSeconds $StableSeconds
        $backup = New-FullBackup -CurrentPackage $preflight.CurrentPackage -Stage $preflight.Stage
        if (@(Get-CodexProcessInventory).Count -ne 0) { throw "A Codex process restarted after backup." }

        Register-AppxManifest -ManifestPath ([string]$preflight.Stage.TargetManifest)
        $registered = Assert-RegisteredDesktopVersion -ExpectedVersion $script:TargetDesktopVersion
        Assert-Hash -Path (Join-Path ([string]$registered.InstallLocation) "app\resources\codex.exe") -Expected $script:TargetCoreHash -Label "Registered Codex core"
        $backup.Data.AppxSwitchCommitted = $true
        Save-BackupManifest -Backup $backup
        Write-SwitchLog -Level "OK" -Message "STAGED_BUILD_SWITCH_OK"

        $cache = Install-PersonalBrowser -SourceRoot $script:StagePluginRoot -ExpectedVersion ([string]$preflight.Stage.PluginVersion) -ExpectedBrowserHash $script:TargetBrowserClientHash
        $backup.Data.PersonalPluginCommitted = $true
        $backup.Data.InstalledPersonalBrowserCache = $cache
        Save-BackupManifest -Backup $backup
        Write-SwitchLog -Level "OK" -Message "PERSONAL_BROWSER_UPDATE_OK"

        if (@(Get-CodexProcessInventory).Count -ne 0) { throw "A Codex process remains after the plugin install command." }
        Write-SwitchLog -Level "OK" -Message "CONVERSATION_BACKUP_OK"
        Write-SwitchLog -Level "OK" -Message "SAFE_TO_REOPEN_CODEX"
    } catch {
        Write-SwitchLog -Level "ERROR" -Message $_.Exception.Message
        if ($null -ne $backup) { Write-SwitchLog -Level "WARN" -Message ("RECOVERY_BACKUP_PATH={0}" -f $backup.Path) }
        Write-SwitchLog -Level "ERROR" -Message "STAGED_BUILD_UPGRADE_FAILED"
        throw
    } finally {
        Exit-SwitchLock
    }
}

function Find-RollbackBackup {
    if (-not [string]::IsNullOrWhiteSpace($BackupPath)) {
        $selected = Get-FullPath -Path $BackupPath
        Assert-PathUnderRoot -Path $selected -Root $script:BackupRoot -Label "Rollback backup"
        return $selected
    }
    if (-not (Test-Path -LiteralPath $script:BackupRoot -PathType Container)) { throw "No staged-build backup root exists." }
    $candidate = Get-ChildItem -LiteralPath $script:BackupRoot -Directory | Sort-Object Name -Descending | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName "switch-manifest.json") -PathType Leaf
    } | Select-Object -First 1
    if ($null -eq $candidate) { throw "No staged-build rollback backup was found." }
    return $candidate.FullName
}

function Restore-OriginalAppx {
    param(
        [string]$SelectedBackup,
        [object]$Manifest
    )

    $expected = [string]$Manifest.OriginalDesktopVersion
    $already = @(Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction SilentlyContinue | Where-Object { [string]$_.Version -eq $expected })
    if ($already.Count -gt 0) { return $already[0] }

    $candidates = @(
        (Join-Path ([string]$Manifest.OriginalInstallLocation) "AppxManifest.xml"),
        (Join-Path $SelectedBackup "appx-package-original\AppxManifest.xml")
    )
    $errors = @()
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        try {
            [xml]$appx = Get-Content -Raw -LiteralPath $candidate
            if ([string]$appx.Package.Identity.Version -ne $expected) { continue }
            Register-AppxManifest -ManifestPath $candidate -AllowDowngrade
            return Assert-RegisteredDesktopVersion -ExpectedVersion $expected
        } catch {
            $errors += "${candidate}: $($_.Exception.Message)"
        }
    }
    throw "Exact AppX rollback was not available. Attempts: $($errors -join ' | ')"
}

function Invoke-Rollback {
    if (-not $ConfirmRollback) { throw "Rollback mode requires -ConfirmRollback." }
    if (Test-RunningInsideCodex) { throw "Rollback must be started from an independent PowerShell window." }

    Enter-SwitchLock
    try {
        $selected = Find-RollbackBackup
        $manifestPath = Join-Path $selected "switch-manifest.json"
        $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
        Wait-ForCodexExit -TimeoutSeconds $WaitTimeoutSeconds -RequiredStableSeconds $StableSeconds

        $registered = Restore-OriginalAppx -SelectedBackup $selected -Manifest $manifest
        Assert-Hash -Path (Join-Path ([string]$registered.InstallLocation) "app\resources\codex.exe") -Expected ([string]$manifest.OriginalCoreHash) -Label "Rolled-back Codex core"

        if ([bool]$manifest.HadPersonalPlugin) {
            $source = Join-Path $selected "personal-plugin-source"
            $expectedVersion = [string]$manifest.OriginalPersonalBrowserVersion
            $expectedHash = Get-Sha256 -Path (Join-Path $source "scripts\browser-client.mjs")
            [void](Install-PersonalBrowser -SourceRoot $source -ExpectedVersion $expectedVersion -ExpectedBrowserHash $expectedHash)
        } else {
            throw "The backup had no prior personal Browser source; automatic plugin rollback is intentionally not destructive."
        }

        Write-SwitchLog -Level "OK" -Message "STAGED_BUILD_ROLLBACK_OK"
        Write-SwitchLog -Level "OK" -Message "CONVERSATION_DATA_PRESERVED"
        Write-SwitchLog -Level "OK" -Message "SAFE_TO_REOPEN_CODEX"
    } catch {
        Write-SwitchLog -Level "ERROR" -Message $_.Exception.Message
        Write-SwitchLog -Level "ERROR" -Message "STAGED_BUILD_ROLLBACK_FAILED"
        throw
    } finally {
        Exit-SwitchLock
    }
}

try {
    Write-SwitchLog -Level "INFO" -Message ("MODE={0} PID={1}" -f $Mode, $PID)
    switch ($Mode) {
        "ProcessScan" {
            Write-CodexProcessInventory -Processes @(Get-CodexProcessInventory)
            if (Test-RunningInsideCodex) {
                Write-SwitchLog -Level "WARN" -Message "RUN_CONTEXT=INSIDE_CODEX_PROCESS_TREE"
            } else {
                Write-SwitchLog -Level "OK" -Message "RUN_CONTEXT=INDEPENDENT_POWERSHELL"
            }
            Write-SwitchLog -Level "OK" -Message "PROCESS_SCAN_OK"
        }
        "Preflight" { [void](Invoke-Preflight) }
        "Upgrade" { Invoke-Upgrade }
        "Rollback" { Invoke-Rollback }
    }
    Write-SwitchLog -Level "INFO" -Message ("LOG_PATH={0}" -f $script:LogPath)
} catch {
    Write-SwitchLog -Level "ERROR" -Message $_.Exception.Message
    Write-SwitchLog -Level "ERROR" -Message ("FAILED_LOG_PATH={0}" -f $script:LogPath)
    Exit-SwitchLock
    exit 1
}
