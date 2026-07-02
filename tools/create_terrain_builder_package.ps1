$ErrorActionPreference = "Stop"

$python = "C:\Users\Adog\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$script = Join-Path $PSScriptRoot "create_terrain_builder_package.py"

& $python $script
