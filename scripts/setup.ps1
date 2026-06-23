$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $PSScriptRoot)

python --version
python -m venv .venv

& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -e .

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run the bot with: .\scripts\start.ps1"
