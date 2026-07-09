# Michigan Mitten 40.96km Plan

## Target

Build the largest practical DayZ terrain for this project: `40960m x 40960m`, or about `1678 km2`.

The first playable pass starts in Detroit. Once that server package boots cleanly, the rest of the lower peninsula becomes a compressed hub-and-highway layout rather than a 1:1 real-world copy.

## Scale Rule

- Terrain size: `40960m`
- Heightmap: `4096 x 4096`
- Cell size: `10m`
- Terrain class: `MichiganMitten`
- First source config: `source-data/michigan-mitten-40960.json`

## Content Rule

- Major cities get downtown or industrial/commercial hubs.
- Towns get small residential/commercial blocks.
- Highways are the navigation skeleton.
- Forest stays prominent between hubs; farmland should support the Michigan feel without taking over the whole map.
- Detroit is the first test-worthy zone.

## First Server Checkpoint

1. Generate Detroit-first 40.96km source exports.
2. Build `terrain/terrain-builder/MichiganMitten`.
3. Carve water and copy source files into `workdrive/MichiganMitten`.
4. Pack/install `MichiganMitten` on the Traverse City, MI server profile.
5. Remove/replace the old `MichiganSurvival` world from the active server configuration.
6. Start through MI Server Manager and verify the server loads `MichiganMitten`.

## Planned Mitten Hubs

These are the intended hub set after the Detroit first pass is booting:

- Detroit
- Ann Arbor
- Flint
- Lansing
- Grand Rapids
- Kalamazoo / Battle Creek
- Saginaw / Bay City / Midland
- Muskegon
- Traverse City
- Alpena
- Mackinaw City

## Highway Skeleton

- I-75
- I-94
- I-96
- I-69
- US-23
- US-131
- US-10
- M-22
- Major Detroit connectors
