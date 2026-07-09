param(
    [string]$ServerRoot = "$env:LOCALAPPDATA\MI Server Manager\servers\Traverse City, MI",
    [string]$MissionName = "dayzOffline.MichiganMitten"
)

$ErrorActionPreference = "Stop"

$missionRoot = Join-Path $ServerRoot "mpmissions\$MissionName"
if (-not (Test-Path -LiteralPath $missionRoot)) {
    throw "Mission folder not found: $missionRoot"
}

$resolvedMission = (Resolve-Path -LiteralPath $missionRoot).Path
$resolvedServer = (Resolve-Path -LiteralPath $ServerRoot).Path
if (-not $resolvedMission.StartsWith($resolvedServer, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Resolved mission path is outside the server root: $resolvedMission"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $missionRoot "_backup_ce_sanitize_$timestamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

function Backup-File {
    param([string]$RelativePath)

    $source = Join-Path $missionRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        return
    }

    $destination = Join-Path $backupRoot $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

function Write-TextFile {
    param(
        [string]$RelativePath,
        [string]$Content
    )

    Backup-File $RelativePath
    $target = Join-Path $missionRoot $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    [System.IO.File]::WriteAllText($target, $Content, [System.Text.Encoding]::UTF8)
}

$emptyMap = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<map>
</map>
'@

$emptyPrototype = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<prototype>
</prototype>
'@

$emptyClusterPrototype = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<prototype>
    <clusters>
    </clusters>
</prototype>
'@

$emptyEventSpawns = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<eventposdef>
</eventposdef>
'@

$emptyEventGroups = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<eventgroupdef>
</eventgroupdef>
'@

$emptyTerritories = @'
<?xml version="1.0" encoding="UTF-8"?>
<territory-type>
</territory-type>
'@

$mapFiles = @(
    "mapgrouppos.xml",
    "mapgroupcluster.xml",
    "mapgroupcluster01.xml",
    "mapgroupcluster02.xml",
    "mapgroupcluster03.xml",
    "mapgroupcluster04.xml"
)

foreach ($file in $mapFiles) {
    Write-TextFile $file $emptyMap
}

Write-TextFile "mapgroupproto.xml" $emptyPrototype
Write-TextFile "mapclusterproto.xml" $emptyClusterPrototype
Write-TextFile "cfgeventspawns.xml" $emptyEventSpawns
Write-TextFile "cfgeventgroups.xml" $emptyEventGroups

Get-ChildItem -LiteralPath (Join-Path $missionRoot "env") -Filter "*territories.xml" -File | ForEach-Object {
    $relative = "env\$($_.Name)"
    Write-TextFile $relative $emptyTerritories
}

$storage = Join-Path $missionRoot "storage_1"
if (Test-Path -LiteralPath $storage) {
    $resolvedStorage = (Resolve-Path -LiteralPath $storage).Path
    if (-not $resolvedStorage.StartsWith($resolvedMission, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to move storage outside mission path: $resolvedStorage"
    }

    $storageBackup = Join-Path $backupRoot "storage_1"
    Move-Item -LiteralPath $storage -Destination $storageBackup
}
New-Item -ItemType Directory -Force -Path $storage | Out-Null

[pscustomobject]@{
    Mission = $missionRoot
    Backup = $backupRoot
    SanitizedMapFiles = $mapFiles.Count
    ResetStorage = $true
}
