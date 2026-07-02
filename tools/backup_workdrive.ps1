$ErrorActionPreference = "Stop"

$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$projectRoot = Join-Path $workspaceRoot "workdrive\MichiganSurvival"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $workspaceRoot "backups\terrain-builder\$timestamp"

if (-not (Test-Path -LiteralPath $projectRoot)) {
    throw "No workdrive project found: $projectRoot"
}

New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
Copy-Item -LiteralPath $projectRoot -Destination (Join-Path $backupRoot "MichiganSurvival") -Recurse -Force
Write-Host "Backed up $projectRoot to $backupRoot"
