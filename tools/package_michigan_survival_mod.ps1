$ErrorActionPreference = "Stop"

$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$workdriveProject = Join-Path $workspaceRoot "workdrive\MichiganSurvival"
$workdriveLayers = Join-Path $workdriveProject "data\layers"
$pboSource = Join-Path $workspaceRoot "build\pbo-src\MichiganSurvival"
$buildMod = Join-Path $workspaceRoot "build\@MichiganSurvival"
$buildAddons = Join-Path $buildMod "Addons"
$buildKeys = Join-Path $buildMod "Keys"
$clientMod = "C:\Program Files (x86)\Steam\steamapps\common\DayZ\@MichiganSurvival"
$serverMod = "C:\Users\Adog\Documents\MI-Server-Manager-2026.05.21.1455\servers\Adog\@MichiganSurvival"
$cfgConvert = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\CfgConvert\CfgConvert.exe"
$fileBank = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\PboUtils\FileBank.exe"
$dsSign = "C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools\Bin\DsUtils\DSSignFile.exe"
$privateKey = Join-Path $workspaceRoot "build\keys\MichiganSurvival.biprivatekey"
$publicKey = Join-Path $workspaceRoot "build\keys\MichiganSurvival.bikey"

foreach ($path in @($workdriveProject, $workdriveLayers, $pboSource, $cfgConvert, $fileBank, $dsSign, $privateKey, $publicKey)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path not found: $path"
    }
}

New-Item -ItemType Directory -Force -Path $buildAddons, $buildKeys | Out-Null

Copy-Item -LiteralPath (Join-Path $workdriveProject "config.cpp") -Destination (Join-Path $pboSource "config.cpp") -Force
Copy-Item -LiteralPath (Join-Path $workdriveProject "world\MichiganSurvival.wrp") -Destination (Join-Path $pboSource "world\MichiganSurvival.wrp") -Force

$scriptTarget = Join-Path $pboSource "scripts"
if (Test-Path -LiteralPath $scriptTarget) {
    Remove-Item -LiteralPath $scriptTarget -Recurse -Force
}

# Keep hand-patched base material files aligned with the active workdrive project.
foreach ($material in @("michigan_grass.rvmat", "michigan_forest.rvmat", "michigan_water.rvmat", "michigan_road.rvmat", "michigan_farmland.rvmat", "michigan_urban.rvmat")) {
    Copy-Item -LiteralPath (Join-Path $workdriveProject "data\$material") -Destination (Join-Path $pboSource "data\$material") -Force
}

$layerTarget = Join-Path $pboSource "data\layers"
if (Test-Path -LiteralPath $layerTarget) {
    Remove-Item -LiteralPath $layerTarget -Recurse -Force
}
Copy-Item -LiteralPath $workdriveLayers -Destination $layerTarget -Recurse -Force

& $cfgConvert -bin -dst (Join-Path $pboSource "config.bin") (Join-Path $pboSource "config.cpp")
if ($LASTEXITCODE -ne 0) {
    throw "CfgConvert failed with exit code $LASTEXITCODE"
}

Remove-Item -LiteralPath (Join-Path $buildAddons "MichiganSurvival.pbo") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $buildAddons "MichiganSurvival.pbo.MichiganSurvival.bisign") -Force -ErrorAction SilentlyContinue

& $fileBank -property "prefix=MichiganSurvival" -dst $buildAddons $pboSource
if ($LASTEXITCODE -ne 0) {
    throw "FileBank failed with exit code $LASTEXITCODE"
}

$pbo = Join-Path $buildAddons "MichiganSurvival.pbo"
if (-not (Test-Path -LiteralPath $pbo)) {
    throw "Expected PBO was not created: $pbo"
}

& $dsSign $privateKey $pbo
if ($LASTEXITCODE -ne 0) {
    throw "DSSignFile failed with exit code $LASTEXITCODE"
}

Copy-Item -LiteralPath $publicKey -Destination (Join-Path $buildKeys "MichiganSurvival.bikey") -Force

foreach ($target in @($clientMod, $serverMod)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $target "Addons"), (Join-Path $target "Keys") | Out-Null
    Copy-Item -LiteralPath $pbo -Destination (Join-Path $target "Addons\MichiganSurvival.pbo") -Force
    Copy-Item -LiteralPath (Join-Path $buildAddons "MichiganSurvival.pbo.MichiganSurvival.bisign") -Destination (Join-Path $target "Addons\MichiganSurvival.pbo.MichiganSurvival.bisign") -Force
    Copy-Item -LiteralPath (Join-Path $buildKeys "MichiganSurvival.bikey") -Destination (Join-Path $target "Keys\MichiganSurvival.bikey") -Force
    Copy-Item -LiteralPath (Join-Path $buildMod "mod.cpp") -Destination (Join-Path $target "mod.cpp") -Force
}

$hash = Get-FileHash -LiteralPath $pbo -Algorithm SHA256
[pscustomobject]@{
    Pbo = $pbo
    Bytes = (Get-Item -LiteralPath $pbo).Length
    Sha256 = $hash.Hash
    ClientMod = $clientMod
    ServerMod = $serverMod
} | Format-List
