param(
    [switch]$DownloadOnly
)

$ErrorActionPreference = "Stop"

$python = "C:\Users\Adog\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$script = Join-Path $PSScriptRoot "build_michigan_lower_peninsula.py"
$arguments = @($script)
if ($DownloadOnly) {
    $arguments += "--download-only"
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Lower Peninsula source build failed with exit code $LASTEXITCODE."
}
