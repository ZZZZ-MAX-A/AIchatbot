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

function Mask-Configured {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "not configured"
    }
    return "configured"
}

function Get-ValueOrDefault {
    param(
        [hashtable]$Values,
        [string]$Key,
        [string]$Default = "not set"
    )
    if ($Values.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Values[$Key])) {
        return $Values[$Key]
    }
    return $Default
}

function Read-DotEnv {
    param([string]$Path)
    $result = @{}
    if (-not (Test-Path $Path)) {
        return $result
    }
    Get-Content -Path $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line.Split("=", 2)
        $result[$key.Trim()] = $value.Trim()
    }
    return $result
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

$envValues = Read-DotEnv ".env"
if (Test-Path ".env") {
    Write-Check "OK" ".env" "exists"
} else {
    Write-Check "WARN" ".env" "missing; defaults may be used"
}
Write-Check "INFO" "OPENAI_API_KEY" (Mask-Configured $envValues["OPENAI_API_KEY"])
Write-Check "INFO" "OPENAI_BASE_URL" (Get-ValueOrDefault $envValues "OPENAI_BASE_URL")
Write-Check "INFO" "OPENAI_MODEL" (Get-ValueOrDefault $envValues "OPENAI_MODEL")
Write-Check "INFO" "ENABLE_VISION" (Get-ValueOrDefault $envValues "ENABLE_VISION")
Write-Check "INFO" "VISION_MODEL" (Get-ValueOrDefault $envValues "VISION_MODEL")
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_MODELS)) {
    Write-Check "INFO" "current OLLAMA_MODELS" "not set"
} else {
    Write-Check "INFO" "current OLLAMA_MODELS" $env:OLLAMA_MODELS
}

try {
    $importOutput = & .\.venv\Scripts\python.exe -c "import bot; print('bot import OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Check "OK" "bot.py import" "success"
    } else {
        Write-Check "ERR" "bot.py import" (($importOutput | Select-Object -Last 3) -join " ")
    }
} catch {
    Write-Check "ERR" "bot.py import" $_.Exception.Message
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

$port11434 = netstat -ano | Select-String ":11434"
if ($port11434) {
    Write-Check "OK" "ollama port 11434" "present"
} else {
    Write-Check "WARN" "ollama port 11434" "not found"
}

$port8080 = netstat -ano | Select-String ":8080"
if ($port8080) {
    Write-Check "OK" "nonebot port 8080" "present"
} else {
    Write-Check "WARN" "nonebot port 8080" "not found"
}

try {
    $ollamaTags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    $models = @($ollamaTags.models | ForEach-Object { $_.name })
    Write-Check "OK" "ollama api" "ok"
    if ($models -contains "qwen2.5vl:3b") {
        Write-Check "OK" "vision model qwen2.5vl:3b" "exists"
    } else {
        Write-Check "WARN" "vision model qwen2.5vl:3b" "not found in ollama tags"
    }
} catch {
    Write-Check "WARN" "ollama api" $_.Exception.GetType().Name
}

try {
    $dbOutput = & .\.venv\Scripts\python.exe -c "import sqlite3; con=sqlite3.connect('data/chatbot.db'); con.execute('select 1').fetchone(); con.close(); print('database OK')" 2>&1
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
