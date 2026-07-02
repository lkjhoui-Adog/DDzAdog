# Start Over Plan

## Phase 1: Pick The Prototype

Decide whether the first map is:

- Traverse City / Grand Traverse Bay
- Upper Peninsula shoreline
- Detroit industrial edge
- A compressed all-Michigan concept

The first prototype should stay small enough to finish: `10 km x 10 km` or `20 km x 20 km`.

## Phase 2: Rebuild Source Data

Collect:

- DEM height data
- Road vectors
- Water polygons and waterways
- Forest and landuse polygons
- A reference satellite-style image

## Phase 3: QGIS Export

Create:

- Heightmap
- Satellite/reference image
- Surface mask
- Road/water/forest vectors
- Export metadata with map size, cell size, CRS, and bounds

## Phase 4: Terrain Builder

Create the Terrain Builder project, then immediately save and back it up before layer generation.

## Phase 5: DayZ Test Package

Build the smallest possible local mod:

- `config.cpp`
- terrain `.wrp`
- generated layers/materials
- local mission folder
- local server config

