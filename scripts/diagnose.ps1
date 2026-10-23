$ErrorActionPreference = "Continue"

Set-Location -Path (Split-Path -Parent $PSScriptRoot)

function Write-Check {
    param(
        [string]$Status,
        [string]$Name,
        [string]$Detail = ""
    )
    if ($Detail) {
        Write-Host ("[{0}] {1}: {2}" -f $Status, $Name, $Detail)
    } else {
        Write-Host ("[{0}] {1}" -f $Status, $Name)
    }
}

Write-Host "AIchatbot local diagnostics"
Write-Host "==========================="

$root = (Get-Location).Path
Write-Check "OK" "workspace" $root

if (Test-Path ".\.venv\Scripts\python.exe") {
    Write-Check "OK" "virtualenv" ".venv"
    try {
        $pythonVersion = & .\.venv\Scripts\python.exe --version 2>&1
        Write-Check "OK" "python" ($pythonVersion -join " ")
    } catch {
        Write-Check "ERR" "python" $_.Exception.Message
    }
} else {
    Write-Check "ERR" "virtualenv" "missing .venv\Scripts\python.exe"
}

if (Test-Path ".env") {
    Write-Check "OK" ".env" "exists"
} else {
    Write-Check "WARN" ".env" "missing; defaults may be used"
}
$configurationReport = $null
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_MODELS)) {
    Write-Check "INFO" "current OLLAMA_MODELS" "not set"
} else {
    Write-Check "INFO" "current OLLAMA_MODELS" $env:OLLAMA_MODELS
}

try {
    $configurationOutput = & .\.venv\Scripts\python.exe .\scripts\check_configuration.py --json 2>&1
    if ($LASTEXITCODE -eq 0) {
        $configurationReport = ($configurationOutput -join "`n") | ConvertFrom-Json
        Write-Check "OK" "configuration parse" "read-only; Bot and database not imported"
        Write-Check "INFO" "default chat configured" $configurationReport.default_chat.configured.ToString()
        Write-Check "INFO" "vision provider" $configurationReport.vision.provider
        Write-Check "INFO" "Ollama required" $configurationReport.ollama_required.ToString()
        foreach ($issue in $configurationReport.issues) {
            Write-Check "WARN" $issue.key $issue.message
        }
    } else {
        Write-Check "ERR" "configuration parse" ($configurationOutput -join " ")
    }
} catch {
    Write-Check "ERR" "configuration parse" $_.Exception.Message
}

$pythonProcesses = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -like "python*" -or $_.ProcessName -like "uvicorn*"
}
Write-Check "INFO" "python/nonebot process count" ($pythonProcesses.Count.ToString())

$napcatProcesses = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -like "*napcat*" -or $_.ProcessName -like "*qq*"
}
Write-Check "INFO" "napcat/qq process count" ($napcatProcesses.Count.ToString())

$ollamaProcesses = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -like "ollama*"
}
if ($ollamaProcesses.Count -gt 0) {
    Write-Check "OK" "ollama process" ($ollamaProcesses.ProcessName -join ", ")
} else {
    Write-Check "WARN" "ollama process" "not found"
}

if ($null -ne $configurationReport) {
    $botPort = [int]$configurationReport.nonebot_port
    $botPortLines = netstat -ano | Select-String ":$botPort\s"
    Write-Check $(if ($botPortLines) { "OK" } else { "WARN" }) "NoneBot configured port" "$botPort"
    if ($configurationReport.ollama_auto_ensure) {
        try {
            $ollamaTags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
            Write-Check "OK" "required local Ollama API" "reachable; model availability not inferred"
        } catch {
            Write-Check "WARN" "required local Ollama API" $_.Exception.GetType().Name
        }
    } else {
        Write-Check "INFO" "local Ollama API" "not probed; no dependency on the standard local endpoint"
    }
}

try {
    $dbOutput = & .\.venv\Scripts\python.exe -c "import sqlite3; con=sqlite3.connect('file:data/chatbot.db?mode=ro', uri=True); con.execute('select 1').fetchone(); con.close(); print('database OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Check "OK" "sqlite database" "open ok"
    } else {
        Write-Check "ERR" "sqlite database" (($dbOutput | Select-Object -Last 3) -join " ")
    }
} catch {
    Write-Check "ERR" "sqlite database" $_.Exception.Message
}

$errorLog = "logs\ai_chat_error.log"
if (Test-Path $errorLog) {
    $recent = Get-Content -Path $errorLog -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -Last 5
    if ($recent) {
        Write-Check "WARN" "recent ai errors" ("{0} lines" -f $recent.Count)
        $recent | ForEach-Object {
            $line = $_ -replace "https?://\S+", "[redacted-url]"
            $line = $line -replace "(?i)(sk-|ak-)[A-Za-z0-9_-]{10,}", "[redacted-secret]"
            Write-Host ("  - {0}" -f $line)
        }
    } else {
        Write-Check "OK" "recent ai errors" "none"
    }
} else {
    Write-Check "OK" "recent ai errors" "log file missing"
}

Write-Host ""
Write-Host "Diagnostics complete."
