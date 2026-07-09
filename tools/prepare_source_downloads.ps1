param(
    [string]$BoundsFile = "$PSScriptRoot\..\source-data\prototype-bounds.json",
    [string]$OutputDir = "$PSScriptRoot\..\source-data\downloads"
)

$ErrorActionPreference = "Stop"

$bounds = Get-Content -Raw -LiteralPath $BoundsFile | ConvertFrom-Json
$bbox = $bounds.bboxWgs84

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$manifestPath = Join-Path $OutputDir "download-manifest.txt"
$overpassQueryPath = Join-Path $OutputDir "overpass-query.ql"
$osmFile = if ($bounds.osmFile) { $bounds.osmFile } else { "traverse-city-osm-roads-water.json" }
$overpassOutPath = Join-Path $OutputDir $osmFile
$tnmOutPath = Join-Path $OutputDir "usgs-tnm-dem-products.json"

$overpassQuery = @"
[out:json][timeout:180];
(
  way["highway"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["waterway"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["natural"="water"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  relation["natural"="water"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["water"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  relation["water"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["landuse"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  relation["landuse"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  way["natural"="wood"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
  relation["natural"="wood"]($($bbox.south),$($bbox.west),$($bbox.north),$($bbox.east));
);
out body;
>;
out skel qt;
"@

Set-Content -LiteralPath $overpassQueryPath -Value $overpassQuery -Encoding ASCII

$tnmUrl = "https://tnmaccess.nationalmap.gov/api/v1/products?datasets=National%20Elevation%20Dataset%20(NED)%201%2F3%20arc-second&bbox=$($bbox.west),$($bbox.south),$($bbox.east),$($bbox.north)&prodFormats=GeoTIFF&outputFormat=JSON"
$overpassUrl = "https://overpass.kumi.systems/api/interpreter"

$manifest = @"
Project: $($bounds.terrainName)
Prototype: $($bounds.prototypeName)
Center: $($bounds.center.latitude), $($bounds.center.longitude)
Size: $($bounds.sizeKm) km x $($bounds.sizeKm) km
BBOX WGS84: south=$($bbox.south), west=$($bbox.west), north=$($bbox.north), east=$($bbox.east)

USGS TNM DEM product query:
$tnmUrl

Overpass endpoint:
$overpassUrl

Generated Overpass query:
$overpassQueryPath

Expected output files after download:
$tnmOutPath
$overpassOutPath
"@

Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding ASCII

Write-Host "Wrote manifest: $manifestPath"
Write-Host "Wrote Overpass query: $overpassQueryPath"
Write-Host ""
Write-Host "Next download commands:"
Write-Host "Invoke-WebRequest -Uri '$tnmUrl' -OutFile '$tnmOutPath'"
$overpassCommand = "`$query = Get-Content -Raw '$overpassQueryPath'; `$uri = '$($overpassUrl)?data=' + [System.Uri]::EscapeDataString(`$query); Invoke-WebRequest -Uri `$uri -OutFile '$overpassOutPath'"
Write-Host $overpassCommand
