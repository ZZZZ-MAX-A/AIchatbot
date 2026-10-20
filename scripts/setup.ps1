$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $PSScriptRoot)

python --version
if ($LASTEXITCODE -ne 0) { throw "Python is unavailable. Install Python 3.12 or newer and add it to PATH." }
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 or newer is required." }
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }

& .\.venv\Scripts\python.exe -m pip install -U pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed. Check network access and retry setup." }
& .\.venv\Scripts\python.exe -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed. Check the pip output and retry setup." }

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run the bot with: .\scripts\start.ps1"
