$ErrorActionPreference = "Stop"

$qgisPython = "C:\Program Files\QGIS 4.0.3\bin\python-qgis.bat"
$script = Join-Path $PSScriptRoot "create_qgis_project.py"

& $qgisPython $script
