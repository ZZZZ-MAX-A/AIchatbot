[CmdletBinding()]
param(
    [string]$Destination = "AIchatbot-owner-console",
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

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required. Install Git for Windows, reopen PowerShell, and rerun this installer."
}

$destinationPath = if ([System.IO.Path]::IsPathRooted($Destination)) {
    [System.IO.Path]::GetFullPath($Destination)
} else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Destination))
}
if (Test-Path -LiteralPath $destinationPath) {
    throw "Destination already exists; refusing to overwrite it: $destinationPath"
}

Write-Host "Downloading the standalone Owner Console frontend source to $destinationPath"
Invoke-Git -GitArguments @("clone", "--filter=blob:none", "--depth", "1", "--no-checkout", "--branch", $Ref, $RepositoryUrl, $destinationPath)
Invoke-Git -GitArguments @("-C", $destinationPath, "sparse-checkout", "init", "--cone")
Invoke-Git -GitArguments @("-C", $destinationPath, "sparse-checkout", "set", "--cone", "web/owner-console")
Invoke-Git -GitArguments @("-C", $destinationPath, "checkout")

$frontendPath = Join-Path $destinationPath "web\owner-console"
if (-not (Test-Path -LiteralPath (Join-Path $frontendPath "package.json"))) {
    throw "Owner Console package files were not found at $frontendPath"
}

Write-Host ""
Write-Host "This download contains the frontend only; the API backend must run from the core project."
Write-Host "Run npm ci and npm run dev in $frontendPath for local development."
