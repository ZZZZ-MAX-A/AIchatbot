[CmdletBinding()]
param(
    [string]$Destination = "AIchatbot",
    [string]$RepositoryUrl = "https://github.com/ZZZZ-MAX-A/AIchatbot.git",
    [string]$Ref = "main"
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([string[]]$GitArguments)
    & git @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed with exit code ${LASTEXITCODE}: git $($GitArguments -join ' ')"
    }
}

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCommand) {
    throw "Git is required. Install Git for Windows, reopen PowerShell, and rerun this installer."
}

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCommand) {
    $knownOllamaPaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
        (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
    )
    $ollamaCommand = $knownOllamaPaths | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}
if (-not $ollamaCommand) {
    throw "Ollama is required because the core install includes bge-m3 for MemoryRAG. Install Ollama, reopen PowerShell, then rerun this command."
}

$destinationPath = if ([System.IO.Path]::IsPathRooted($Destination)) {
    [System.IO.Path]::GetFullPath($Destination)
} else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Destination))
}
if (Test-Path -LiteralPath $destinationPath) {
    throw "Destination already exists; refusing to overwrite it: $destinationPath"
}

Write-Host "Downloading the core project to $destinationPath"
Invoke-Git -GitArguments @("clone", "--filter=blob:none", "--depth", "1", "--no-checkout", "--branch", $Ref, $RepositoryUrl, $destinationPath)
Invoke-Git -GitArguments @("-C", $destinationPath, "sparse-checkout", "init", "--cone")
Invoke-Git -GitArguments @("-C", $destinationPath, "sparse-checkout", "set", "--cone", "config", "docs", "prompts", "scripts", "src", "tests")
Invoke-Git -GitArguments @("-C", $destinationPath, "checkout")

$frontendPath = Join-Path $destinationPath "web\owner-console"
if (Test-Path -LiteralPath $frontendPath) {
    throw "The core checkout unexpectedly contains the Owner Console frontend: $frontendPath"
}

$envExample = Join-Path $destinationPath ".env.example"
$envPath = Join-Path $destinationPath ".env"
if ((Test-Path -LiteralPath $envExample) -and -not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $envExample -Destination $envPath
    Write-Host "Created .env from .env.example. Edit it before starting the bot."
} elseif (Test-Path -LiteralPath $envPath) {
    Write-Host "Keeping the existing .env file."
}

Write-Host "Downloading the required RAG embedding model. This is the only model pulled by this installer."
& (Join-Path $destinationPath "scripts\install-vector-model.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Required RAG model setup failed. Resolve the error and rerun scripts\install-vector-model.ps1 from the downloaded project."
}

Write-Host ""
Write-Host "Core source and bge-m3 are ready. The web/owner-console frontend was excluded."
Write-Host "Next: edit $envPath, run .\scripts\setup.ps1, then .\scripts\start.ps1."
