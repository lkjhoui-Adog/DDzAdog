$ErrorActionPreference = "Stop"

$rawDir = Resolve-Path (Join-Path $PSScriptRoot "..\source-data")
$tigerDir = Join-Path $rawDir "raw\tiger"
$extractDir = Join-Path $tigerDir "extract"
$geojsonDir = Join-Path $tigerDir "geojson"
$ogr2ogr = "C:\Program Files\QGIS 4.0.3\bin\ogr2ogr.exe"

if (-not (Test-Path -LiteralPath $ogr2ogr)) {
    throw "ogr2ogr not found: $ogr2ogr"
}

New-Item -ItemType Directory -Force -Path $tigerDir, $extractDir, $geojsonDir | Out-Null

$countyFips = "26055"
$sources = @(
    @{
        Name = "roads"
        Url = "https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_${countyFips}_roads.zip"
        Shp = "tl_2025_${countyFips}_roads.shp"
        Out = "tiger_roads.geojson"
    },
    @{
        Name = "areawater"
        Url = "https://www2.census.gov/geo/tiger/TIGER2025/AREAWATER/tl_2025_${countyFips}_areawater.zip"
        Shp = "tl_2025_${countyFips}_areawater.shp"
        Out = "tiger_areawater.geojson"
    },
    @{
        Name = "linearwater"
        Url = "https://www2.census.gov/geo/tiger/TIGER2025/LINEARWATER/tl_2025_${countyFips}_linearwater.zip"
        Shp = "tl_2025_${countyFips}_linearwater.shp"
        Out = "tiger_linearwater.geojson"
    }
)

foreach ($source in $sources) {
    $zipPath = Join-Path $tigerDir "$($source.Name).zip"
    $sourceExtractDir = Join-Path $extractDir $source.Name
    $outPath = Join-Path $geojsonDir $source.Out

    Write-Host "Downloading TIGER $($source.Name)..."
    Invoke-WebRequest -Uri $source.Url -OutFile $zipPath

    if (Test-Path -LiteralPath $sourceExtractDir) {
        Remove-Item -LiteralPath $sourceExtractDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $sourceExtractDir | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $sourceExtractDir -Force

    $shpPath = Join-Path $sourceExtractDir $source.Shp
    if (-not (Test-Path -LiteralPath $shpPath)) {
        throw "Expected shapefile missing: $shpPath"
    }

    Write-Host "Converting TIGER $($source.Name) to GeoJSON..."
    & $ogr2ogr -f GeoJSON -t_srs EPSG:4326 $outPath $shpPath
}

Write-Host "TIGER GeoJSON written to $geojsonDir"
