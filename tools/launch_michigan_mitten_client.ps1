param(
    [string]$ServerRoot = "C:\Users\Adog\AppData\Local\MI Server Manager\servers\Traverse City, MI",
    [string]$DayZRoot = "C:\Program Files (x86)\Steam\steamapps\common\DayZ",
    [string]$Connect = "127.0.0.1:2302:27016",
    [string]$ProfileName = "-DDz-AdogASC",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$modsJson = Join-Path $ServerRoot "mods.json"
$beExe = Join-Path $DayZRoot "DayZ_BE.exe"

foreach ($requiredPath in @($modsJson, $beExe)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required path not found: $requiredPath"
    }
}

$mods = Get-Content -LiteralPath $modsJson -Raw | ConvertFrom-Json
$enabledMods = @(
    $mods |
        Where-Object { $_.Enabled -and $_.Type -eq "Client" } |
        Sort-Object LoadOrder
)

$modPaths = New-Object System.Collections.Generic.List[string]
$missing = New-Object System.Collections.Generic.List[string]

foreach ($mod in $enabledMods) {
    $folder = [string]$mod.FolderName
    $workshopId = [string]$mod.WorkshopID
    if ([string]::IsNullOrWhiteSpace($folder)) {
        continue
    }

    $localPath = Join-Path $DayZRoot "@$folder"
    $workshopPath = Join-Path (Join-Path $DayZRoot "!Workshop") "@$folder"

    if (([string]::IsNullOrWhiteSpace($workshopId) -or $workshopId.StartsWith("local", [System.StringComparison]::OrdinalIgnoreCase)) -and (Test-Path -LiteralPath $localPath)) {
        $modPaths.Add($localPath)
    } elseif (Test-Path -LiteralPath $workshopPath) {
        $modPaths.Add($workshopPath)
    } elseif (Test-Path -LiteralPath $localPath) {
        $modPaths.Add($localPath)
    } else {
        $missing.Add($folder)
    }
}

if ($missing.Count -gt 0) {
    throw "Missing client mod folder(s): $($missing -join ', ')"
}

$modArg = "-mod=$($modPaths -join ';')"
$arguments = '0 1 1 -exe DayZ_x64.exe -name="{0}" "{1}" -connect={2}' -f $ProfileName, $modArg, $Connect

Write-Host "Launching DayZ with $($modPaths.Count) mods."
Write-Host $arguments
if ($DryRun) {
    return
}

Start-Process -FilePath $beExe -WorkingDirectory $DayZRoot -ArgumentList $arguments
