[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:11434",
    [ValidateRange(1, 600)]
    [int]$StartupWaitSeconds = 60
)

$ErrorActionPreference = "Stop"
$Model = "bge-m3"

function Write-InstallStatus {
    param(
        [string]$Status,
        [string]$Message
    )
    Write-Host ("[{0}] {1}" -f $Status, $Message)
}

function Get-OllamaTags {
    param([string]$Url)
    return Invoke-RestMethod -Uri ($Url.TrimEnd("/") + "/api/tags") -TimeoutSec 3
}

function Get-OllamaModelNames {
    param($Tags)
    if ($null -eq $Tags -or $null -eq $Tags.models) {
        return @()
    }
    return @($Tags.models | ForEach-Object { [string]$_.name } | Where-Object { $_ })
}

function Test-ModelPresent {
    param(
        [string[]]$Models,
        [string]$Expected
    )
    foreach ($name in $Models) {
        if ($name -eq $Expected -or ($Expected -notlike "*:*" -and $name -eq "${Expected}:latest")) {
            return $true
        }
    }
    return $false
}

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExecutable = if ($ollamaCommand) { $ollamaCommand.Source } else { "" }
if (-not $ollamaExecutable) {
    $knownPaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
        (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
    )
    $ollamaPath = $knownPaths | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if ($ollamaPath) {
        $ollamaExecutable = $ollamaPath
    }
}

if (-not $ollamaExecutable) {
    throw "Ollama is required to download the RAG embedding model. Install Ollama, reopen PowerShell, then rerun .\scripts\install-vector-model.ps1."
}

try {
    $uri = [Uri]$BaseUrl
} catch {
    throw "Invalid Ollama URL: $BaseUrl"
}

if ($uri.Scheme -notin @("http", "https")) {
    throw "Ollama URL must use HTTP or HTTPS: $BaseUrl"
}
if (-not $uri.IsAbsoluteUri -or $uri.AbsolutePath -ne "/" -or $uri.Query -or $uri.Fragment -or $uri.UserInfo) {
    throw "Ollama URL must be an absolute service URL without a path, query, fragment, or credentials: $BaseUrl"
}

# Ensure both the CLI pull and any new server use the same endpoint as the API.
$previousOllamaHost = $env:OLLAMA_HOST
try {
    $env:OLLAMA_HOST = $uri.GetLeftPart([System.UriPartial]::Authority)
    $isLoopback = $uri.Host -in @("127.0.0.1", "localhost", "::1")
    $tags = $null
    try {
        $tags = Get-OllamaTags -Url $BaseUrl
    } catch {
        if (-not $isLoopback) {
            throw "Ollama is not reachable at $BaseUrl. Start that Ollama service and retry. $($_.Exception.Message)"
        }

        $listener = @()
        try {
            $listener = @(
                Get-NetTCPConnection -LocalPort $uri.Port -State Listen -ErrorAction Stop
            )
        } catch {
            $listener = @()
        }
        if ($listener.Count -gt 0) {
            throw "A service is listening at $BaseUrl but did not return the Ollama tags API. Refusing to replace or restart it."
        }

        Write-InstallStatus "INFO" "Starting the local Ollama service."
        Start-Process -FilePath $ollamaExecutable -ArgumentList "serve" -WindowStyle Hidden
        $deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
        do {
            Start-Sleep -Seconds 1
            try {
                $tags = Get-OllamaTags -Url $BaseUrl
                break
            } catch {
                if ((Get-Date) -ge $deadline) {
                    throw "Ollama did not become ready at $BaseUrl within $StartupWaitSeconds seconds. $($_.Exception.Message)"
                }
            }
        } while ($true)
    }

    $presentModels = Get-OllamaModelNames -Tags $tags
    if (Test-ModelPresent -Models $presentModels -Expected $Model) {
        Write-InstallStatus "OK" "Required RAG model is already installed: $Model"
    } else {
        Write-InstallStatus "INFO" "Downloading the required RAG embedding model: $Model"
        & $ollamaExecutable pull $Model
        if ($LASTEXITCODE -ne 0) {
            throw "Ollama failed to download $Model (exit code $LASTEXITCODE). Rerun .\scripts\install-vector-model.ps1 after resolving the Ollama or network issue."
        }

        $tags = Get-OllamaTags -Url $BaseUrl
        $presentModels = Get-OllamaModelNames -Tags $tags
        if (-not (Test-ModelPresent -Models $presentModels -Expected $Model)) {
            throw "Ollama pull completed, but $Model is not visible from $BaseUrl/api/tags."
        }
    }

    # Run the same CPU embedding path as the deployment template, including when
    # the model was already installed. Tags alone cannot prove it can be loaded.
    $payload = @{
        model = $Model
        input = "MemoryRAG installation check"
        options = @{ num_gpu = 0 }
    } | ConvertTo-Json -Depth 4 -Compress
    $embedding = Invoke-RestMethod -Method Post -Uri ($BaseUrl.TrimEnd("/") + "/api/embed") -ContentType "application/json" -Body $payload -TimeoutSec 180
    if ($null -eq $embedding.embeddings -or $embedding.embeddings.Count -ne 1 -or $embedding.embeddings[0].Count -ne 1024) {
        throw "The required bge-m3 model did not return one 1024-dimensional embedding. RAG setup is incomplete."
    }
    Write-InstallStatus "OK" "Required RAG model is ready: $Model (1024-dimensional CPU embedding verified)."
} finally {
    if ($null -eq $previousOllamaHost) {
        Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue
    } else {
        $env:OLLAMA_HOST = $previousOllamaHost
    }
}
