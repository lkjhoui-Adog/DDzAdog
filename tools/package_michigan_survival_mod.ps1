param(
    [string]$TerrainName = "MichiganSurvival",
    [string]$KeyName = $TerrainName,
    [string]$ServerRoot = "C:\Users\Adog\AppData\Local\MI Server Manager\servers\Traverse City, MI",
    [string]$ClientDayZRoot = "C:\Program Files (x86)\Steam\steamapps\common\DayZ",
    [string]$WorkdriveProject = "",
    [switch]$BuildOnly
)

$ErrorActionPreference = "Stop"

$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$workdriveProject = if ($WorkdriveProject) {
    $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($WorkdriveProject)
} else {
    Join-Path $workspaceRoot "workdrive\$TerrainName"
}
$workdriveLayers = Join-Path $workdriveProject "data\layers"
$pboSource = Join-Path $workspaceRoot "build\pbo-src\$TerrainName"
$buildMod = Join-Path $workspaceRoot "build\@$TerrainName"
$buildAddons = Join-Path $buildMod "Addons"
$buildKeys = Join-Path $buildMod "Keys"
$clientMod = Join-Path $ClientDayZRoot "@$TerrainName"
$serverMod = Join-Path $ServerRoot "@$TerrainName"
$cfgConvert = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\CfgConvert\CfgConvert.exe"
$imageToPaa = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\ImageToPAA\ImageToPAA.exe"
$fileBank = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\PboUtils\FileBank.exe"
$dsCreateKey = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\DsUtils\DSCreateKey.exe"
$dsSign = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\DsUtils\DSSignFile.exe"
$keysDir = Join-Path $workspaceRoot "build\keys"
$privateKey = Join-Path $keysDir "$KeyName.biprivatekey"
$publicKey = Join-Path $keysDir "$KeyName.bikey"

foreach ($path in @($workdriveProject, $cfgConvert, $imageToPaa, $fileBank, $dsCreateKey, $dsSign)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path not found: $path"
    }
}

$resolvedWorkspaceRoot = [System.IO.Path]::GetFullPath($workspaceRoot.Path).TrimEnd('\') + '\'
$resolvedPboSource = [System.IO.Path]::GetFullPath($pboSource)
if (-not $resolvedPboSource.StartsWith($resolvedWorkspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean PBO source outside the workspace: $resolvedPboSource"
}
if (Test-Path -LiteralPath $resolvedPboSource) {
    Remove-Item -LiteralPath $resolvedPboSource -Recurse -Force
}

$wrp = Join-Path $workdriveProject "world\$TerrainName.wrp"
if (-not (Test-Path -LiteralPath $wrp)) {
    throw "Required world file not found: $wrp. Export/save the terrain from Terrain Builder first."
}
if (-not (Test-Path -LiteralPath $workdriveLayers)) {
    throw "Required terrain layers folder not found: $workdriveLayers. Generate layers in Terrain Builder first."
}

$terrainTextures = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($textureName in @("S_full_lco", "M_full_lca", "M_base_lca")) {
    $null = $terrainTextures.Add($textureName)
}
Get-ChildItem -LiteralPath $workdriveLayers -Filter "P_*.rvmat" -File | ForEach-Object {
    if ($_.Name -match '^P_(\d{3})-(\d{3})_') {
        $null = $terrainTextures.Add("S_$($Matches[1])_$($Matches[2])_lco")
    }
}

foreach ($textureName in $terrainTextures) {
    $png = Join-Path $workdriveLayers "$textureName.png"
    $paa = Join-Path $workdriveLayers "$textureName.paa"
    if (-not (Test-Path -LiteralPath $png)) {
        throw "Required terrain texture not found: $png"
    }
    & $imageToPaa $png $paa
    if ($LASTEXITCODE -ne 0) {
        throw "ImageToPAA failed for $png with exit code $LASTEXITCODE"
    }
}

New-Item -ItemType Directory -Force -Path $buildAddons, $buildKeys, $keysDir, (Join-Path $pboSource "world"), (Join-Path $pboSource "data") | Out-Null

if (-not (Test-Path -LiteralPath $privateKey) -or -not (Test-Path -LiteralPath $publicKey)) {
    Push-Location $keysDir
    try {
        & $dsCreateKey $KeyName
        if ($LASTEXITCODE -ne 0) {
            throw "DSCreateKey failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

Copy-Item -LiteralPath (Join-Path $workdriveProject "config.cpp") -Destination (Join-Path $pboSource "config.cpp") -Force
Copy-Item -LiteralPath $wrp -Destination (Join-Path $pboSource "world\$TerrainName.wrp") -Force

$navmeshTarget = Join-Path $pboSource "navmesh"
if (Test-Path -LiteralPath $navmeshTarget) {
    Remove-Item -LiteralPath $navmeshTarget -Recurse -Force
}
$navmeshSource = Join-Path $workdriveProject "navmesh"
$navmeshFile = Join-Path $navmeshSource "navmesh.nm"
if (Test-Path -LiteralPath $navmeshFile) {
    New-Item -ItemType Directory -Force -Path $navmeshTarget | Out-Null
    Copy-Item -LiteralPath $navmeshFile -Destination (Join-Path $navmeshTarget "navmesh.nm") -Force
}

$scriptTarget = Join-Path $pboSource "scripts"
if (Test-Path -LiteralPath $scriptTarget) {
    Remove-Item -LiteralPath $scriptTarget -Recurse -Force
}
$scriptSource = Join-Path $workdriveProject "scripts"
if (Test-Path -LiteralPath $scriptSource) {
    Copy-Item -LiteralPath $scriptSource -Destination $scriptTarget -Recurse -Force
}

Get-ChildItem -LiteralPath (Join-Path $workdriveProject "data") -Filter "*.rvmat" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $pboSource "data\$($_.Name)") -Force
}

$layerTarget = Join-Path $pboSource "data\layers"
New-Item -ItemType Directory -Force -Path $layerTarget | Out-Null
Get-ChildItem -LiteralPath $workdriveLayers -File | Where-Object {
    $_.Extension -in @(".paa", ".rvmat")
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $layerTarget $_.Name) -Force
}

$modCpp = Join-Path $buildMod "mod.cpp"
if (-not (Test-Path -LiteralPath $modCpp)) {
    @"
name = "$TerrainName";
picture = "";
logo = "";
logoSmall = "";
logoOver = "";
tooltip = "$TerrainName";
overview = "$TerrainName custom DayZ terrain.";
action = "";
author = "Adog";
version = "0.1";
"@ | Set-Content -LiteralPath $modCpp -Encoding ASCII
}

& $cfgConvert -bin -dst (Join-Path $pboSource "config.bin") (Join-Path $pboSource "config.cpp")
if ($LASTEXITCODE -ne 0) {
    throw "CfgConvert failed with exit code $LASTEXITCODE"
}

Remove-Item -LiteralPath (Join-Path $buildAddons "$TerrainName.pbo") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $buildAddons "$TerrainName.pbo.$KeyName.bisign") -Force -ErrorAction SilentlyContinue

& $fileBank -property "prefix=$TerrainName" -dst $buildAddons $pboSource
if ($LASTEXITCODE -ne 0) {
    throw "FileBank failed with exit code $LASTEXITCODE"
}

$pbo = Join-Path $buildAddons "$TerrainName.pbo"
if (-not (Test-Path -LiteralPath $pbo)) {
    throw "Expected PBO was not created: $pbo"
}

& $dsSign $privateKey $pbo
if ($LASTEXITCODE -ne 0) {
    throw "DSSignFile failed with exit code $LASTEXITCODE"
}

$bisign = Join-Path $buildAddons "$TerrainName.pbo.$KeyName.bisign"
Copy-Item -LiteralPath $publicKey -Destination (Join-Path $buildKeys "$KeyName.bikey") -Force

if (-not $BuildOnly) {
    foreach ($target in @($clientMod, $serverMod)) {
        New-Item -ItemType Directory -Force -Path (Join-Path $target "Addons"), (Join-Path $target "Keys") | Out-Null
        Copy-Item -LiteralPath $pbo -Destination (Join-Path $target "Addons\$TerrainName.pbo") -Force
        Copy-Item -LiteralPath $bisign -Destination (Join-Path $target "Addons\$TerrainName.pbo.$KeyName.bisign") -Force
        Copy-Item -LiteralPath (Join-Path $buildKeys "$KeyName.bikey") -Destination (Join-Path $target "Keys\$KeyName.bikey") -Force
        Copy-Item -LiteralPath $modCpp -Destination (Join-Path $target "mod.cpp") -Force
    }

    $serverKeys = Join-Path $ServerRoot "keys"
    if (Test-Path -LiteralPath $serverKeys) {
        Copy-Item -LiteralPath $publicKey -Destination (Join-Path $serverKeys "$KeyName.bikey") -Force
    }
}

$hash = Get-FileHash -LiteralPath $pbo -Algorithm SHA256
[pscustomobject]@{
    TerrainName = $TerrainName
    Pbo = $pbo
    Bytes = (Get-Item -LiteralPath $pbo).Length
    Sha256 = $hash.Hash
    Installed = -not $BuildOnly
    ClientMod = $clientMod
    ServerMod = $serverMod
} | Format-List
