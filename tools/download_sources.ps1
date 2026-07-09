param(
    [string]$BoundsFile = "$PSScriptRoot\..\source-data\prototype-bounds.json",
    [string]$OutputDir = "$PSScriptRoot\..\source-data\downloads"
)

$ErrorActionPreference = "Stop"

$bounds = Get-Content -Raw -LiteralPath $BoundsFile | ConvertFrom-Json
$bbox = $bounds.bboxWgs84

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$tnmOutPath = Join-Path $OutputDir "usgs-tnm-dem-products.json"
$overpassQueryPath = Join-Path $OutputDir "overpass-query.ql"
$osmFile = if ($bounds.osmFile) { $bounds.osmFile } else { "traverse-city-osm-roads-water.json" }
$overpassOutPath = Join-Path $OutputDir $osmFile

if (-not (Test-Path -LiteralPath $overpassQueryPath)) {
    & (Join-Path $PSScriptRoot "prepare_source_downloads.ps1") -BoundsFile $BoundsFile -OutputDir $OutputDir
}

$tnmUrl = "https://tnmaccess.nationalmap.gov/api/v1/products?datasets=National%20Elevation%20Dataset%20(NED)%201%2F3%20arc-second&bbox=$($bbox.west),$($bbox.south),$($bbox.east),$($bbox.north)&prodFormats=GeoTIFF&outputFormat=JSON"
Write-Host "Downloading USGS DEM product metadata..."
Invoke-WebRequest -Uri $tnmUrl -OutFile $tnmOutPath

$queries = @(
    @{
        Name = "roads"
        Query = @"
[out:json][timeout:180];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|living_street)$"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
);
out body;
>;
out skel qt;
"@
    },
    @{
        Name = "water"
        Query = @"
[out:json][timeout:180];
(
  way["waterway"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["natural"="water"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["water"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
);
out body;
>;
out skel qt;
"@
    },
    @{
        Name = "landuse"
        Query = @"
[out:json][timeout:180];
(
  way["landuse"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["natural"="wood"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
);
out body;
>;
out skel qt;
"@
    }
)

$endpoints = @(
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
)

$merged = [ordered]@{
    version = 0.6
    generator = "MichiganSurvival split Overpass downloader"
    elements = @()
}
$seen = @{}

foreach ($queryInfo in $queries) {
    $partPath = Join-Path $OutputDir "overpass-$($queryInfo.Name).json"
    $success = $false
    foreach ($endpoint in $endpoints) {
        try {
            Write-Host "Downloading OSM $($queryInfo.Name) data from $endpoint..."
            $body = "data=" + [System.Uri]::EscapeDataString($queryInfo.Query)
            Invoke-WebRequest -Uri $endpoint -Method Post -ContentType "application/x-www-form-urlencoded" -Body $body -OutFile $partPath
            $success = $true
            break
        } catch {
            Write-Warning "OSM $($queryInfo.Name) failed at ${endpoint}: $($_.Exception.Message)"
        }
    }
    if (-not $success) {
        throw "Could not download OSM $($queryInfo.Name) data from any endpoint."
    }

    $part = Get-Content -Raw -LiteralPath $partPath | ConvertFrom-Json
    foreach ($element in @($part.elements)) {
        $key = "$($element.type):$($element.id)"
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            $merged.elements += $element
        }
    }
}

$merged | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $overpassOutPath -Encoding UTF8

Write-Host "Wrote $tnmOutPath"
Write-Host "Wrote $overpassOutPath"
