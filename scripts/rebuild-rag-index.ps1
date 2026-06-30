param(
    [switch]$ProjectDocs,
    [string]$QueryProjectDocs = "",
    [string]$Root = "",
    [int]$MaxChars = 1800,
    [int]$TopK = 0,
    [double]$MinScore = -1,
    [int]$MaxContextChars = 0,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $Python) {
    $Python = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$scriptPath = Join-Path $PSScriptRoot "rebuild_rag_index.py"
$arguments = @($scriptPath)

if ($ProjectDocs) {
    $arguments += "--project-docs"
}
if ($QueryProjectDocs) {
    $arguments += "--query-project-docs"
    $arguments += $QueryProjectDocs
}
if ($Root) {
    $arguments += "--root"
    $arguments += $Root
}
if ($MaxChars -gt 0) {
    $arguments += "--max-chars"
    $arguments += $MaxChars.ToString()
}
if ($TopK -gt 0) {
    $arguments += "--top-k"
    $arguments += $TopK.ToString()
}
if ($MinScore -ge 0) {
    $arguments += "--min-score"
    $arguments += $MinScore.ToString()
}
if ($MaxContextChars -gt 0) {
    $arguments += "--max-context-chars"
    $arguments += $MaxContextChars.ToString()
}

& $Python @arguments
exit $LASTEXITCODE
