# DayZ Michigan Map

Fresh start for a custom DayZ terrain inspired by Michigan.

## Goal

Build a playable Michigan-inspired DayZ map in stages:

1. Choose one prototype region.
2. Gather clean terrain source data.
3. Build QGIS exports.
4. Import into Terrain Builder.
5. Package a minimal DayZ terrain mod.
6. Launch a local test server and iterate.

## Clean Workspace Layout

- `docs/` - planning and pipeline notes
- `source-data/` - downloaded DEM, OSM, imagery, and raw data notes
- `terrain/` - QGIS projects, exported rasters/vectors, and Terrain Builder packages
- `objects/` - object placement plans and later generated placement data
- `server-files/` - mission, economy, spawn, and local server config files
- `tools/` - scripts for repeatable downloads, exports, packaging, and validation
- `workdrive/` - local folder mounted as `P:` for DayZ Tools work

## First Rule

No manual-only progress. Every major step should produce a saved file, script, checklist, or backup so we do not lose work again.

