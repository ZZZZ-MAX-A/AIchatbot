$workdir = "D:\AIchatbot\tools\UVR5"
$uvr = Join-Path $workdir "UVR.exe"

if (-not (Test-Path -LiteralPath $uvr)) {
    Write-Host "UVR.exe was not found: $uvr"
    exit 1
}

$env:TCL_LIBRARY = Join-Path $workdir "tcl"
$env:TK_LIBRARY = Join-Path $workdir "tk"
$env:PATH = "$workdir;$env:PATH"

Start-Process -FilePath $uvr -WorkingDirectory $workdir
