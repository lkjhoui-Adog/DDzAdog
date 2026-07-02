$ErrorActionPreference = "Stop"

$python = "C:\Users\Adog\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$script = Join-Path $PSScriptRoot "process_sources.py"

& $python $script
