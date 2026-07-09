# Tools

This folder is intentionally clean after the reset.

Add scripts here only when they make the rebuild repeatable.

## MichiganMitten 40.96km Build Commands

Run GIS Python commands with QGIS PROJ data available:

```powershell
$env:PROJ_LIB = "C:\Program Files\QGIS 4.0.3\share\proj"
$env:PROJ_DATA = $env:PROJ_LIB
$py = "C:\Program Files\QGIS 4.0.3\apps\Python312\python.exe"
```

Prepare/download source data:

```powershell
.\tools\download_sources.ps1 `
  -BoundsFile .\source-data\michigan-mitten-40960.json `
  -OutputDir .\source-data\downloads\michigan-mitten
```

Process and package:

```powershell
& $py .\tools\process_sources.py `
  --bounds-file .\source-data\michigan-mitten-40960.json `
  --downloads-dir .\source-data\downloads\michigan-mitten `
  --raw-elevation-dir .\source-data\raw\elevation\michigan-mitten `
  --gis-dir .\terrain\gis\michigan-mitten `
  --export-root .\terrain\exports\michigan-mitten

& $py .\tools\create_terrain_builder_package.py `
  --export-root .\terrain\exports\michigan-mitten

& $py .\tools\carve_water_heightmap.py `
  --export-root .\terrain\exports\michigan-mitten
```
