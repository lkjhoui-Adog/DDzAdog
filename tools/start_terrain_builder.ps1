param(
    [string]$TerrainName = "MichiganSurvival"
)

$ErrorActionPreference = "Stop"

$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$workdriveRoot = Join-Path $workspaceRoot "workdrive"
$sourceProject = Join-Path $workspaceRoot "terrain\terrain-builder\$TerrainName"
$targetProject = Join-Path $workdriveRoot $TerrainName
$terrainBuilderExe = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\TerrainBuilder\terrainBuilder.exe"

if (-not (Test-Path -LiteralPath $terrainBuilderExe)) {
    throw "Terrain Builder not found: $terrainBuilderExe"
}

New-Item -ItemType Directory -Force -Path $workdriveRoot | Out-Null

$subst = cmd /c subst
if ($subst -match "^P:\\") {
    cmd /c "subst P: /D" | Out-Null
}
cmd /c "subst P: `"$workdriveRoot`"" | Out-Null

New-Item -ItemType Directory -Force -Path $targetProject | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceProject "*") -Destination $targetProject -Recurse -Force

Start-Process -FilePath $terrainBuilderExe -WorkingDirectory (Split-Path -Parent $terrainBuilderExe)
Write-Host "Mounted P: to $workdriveRoot"
Write-Host "Synced $sourceProject to $targetProject"
Write-Host "Launched Terrain Builder"
