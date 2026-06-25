$root = "D:\AIchatbot"
$workdir = Join-Path $root "tts-validation\index-tts-main"
$python = Join-Path $workdir ".venv\Scripts\python.exe"
$service = Join-Path $root "src\plugins\ai_chat\tts_service.py"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "IndexTTS2 python was not found: $python"
    exit 1
}

if (-not (Test-Path -LiteralPath $service)) {
    Write-Host "TTS service script was not found: $service"
    exit 1
}

Set-Location -LiteralPath $workdir
& $python $service
