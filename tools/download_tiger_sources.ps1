param(
    [string[]]$CountyFips = @("26055"),
    [string]$TigerDir = "$PSScriptRoot\..\source-data\raw\tiger"
)

$ErrorActionPreference = "Stop"

$CountyFips = @(
    foreach ($county in $CountyFips) {
        foreach ($part in ($county -split ",")) {
            $trimmed = $part.Trim()
            if ($trimmed) { $trimmed }
        }
    }
)

$tigerDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($TigerDir)
$extractDir = Join-Path $tigerDir "extract"
$geojsonDir = Join-Path $tigerDir "geojson"
$ogr2ogr = "C:\Program Files\QGIS 4.0.3\bin\ogr2ogr.exe"

if (-not (Test-Path -LiteralPath $ogr2ogr)) {
    throw "ogr2ogr not found: $ogr2ogr"
}

New-Item -ItemType Directory -Force -Path $tigerDir, $extractDir, $geojsonDir | Out-Null

$sources = @(
    @{
        Name = "roads"
        Folder = "ROADS"
        ShpSuffix = "roads"
        Out = "tiger_roads.geojson"
    },
    @{
        Name = "areawater"
        Folder = "AREAWATER"
        ShpSuffix = "areawater"
        Out = "tiger_areawater.geojson"
    },
    @{
        Name = "linearwater"
        Folder = "LINEARWATER"
        ShpSuffix = "linearwater"
        Out = "tiger_linearwater.geojson"
    }
)

foreach ($source in $sources) {
    $merged = [ordered]@{
        type = "FeatureCollection"
        name = $source.Out.Replace(".geojson", "")
        features = @()
    }

    foreach ($countyFips in $CountyFips) {
        $zipPath = Join-Path $tigerDir "$($source.Name)_${countyFips}.zip"
        $sourceExtractDir = Join-Path $extractDir "$($source.Name)_${countyFips}"
        $tempPath = Join-Path $geojsonDir "temp_$($source.Name)_${countyFips}.geojson"
        $url = "https://www2.census.gov/geo/tiger/TIGER2025/$($source.Folder)/tl_2025_${countyFips}_$($source.ShpSuffix).zip"

        Write-Host "Downloading TIGER $($source.Name) for county $countyFips..."
        Invoke-WebRequest -Uri $url -OutFile $zipPath

        if (Test-Path -LiteralPath $sourceExtractDir) {
            Remove-Item -LiteralPath $sourceExtractDir -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path $sourceExtractDir | Out-Null
        Expand-Archive -LiteralPath $zipPath -DestinationPath $sourceExtractDir -Force

        $shpPath = Join-Path $sourceExtractDir "tl_2025_${countyFips}_$($source.ShpSuffix).shp"
        if (-not (Test-Path -LiteralPath $shpPath)) {
            throw "Expected shapefile missing: $shpPath"
        }

        Write-Host "Converting TIGER $($source.Name) county $countyFips to GeoJSON..."
        & $ogr2ogr -f GeoJSON -t_srs EPSG:4326 $tempPath $shpPath

        $data = Get-Content -Raw -LiteralPath $tempPath | ConvertFrom-Json
        $merged.features += @($data.features)
    }

    $outPath = Join-Path $geojsonDir $source.Out
    $merged | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $outPath -Encoding UTF8
    Write-Host "Merged TIGER $($source.Name) written to $outPath"
}

Write-Host "TIGER GeoJSON written to $geojsonDir"
