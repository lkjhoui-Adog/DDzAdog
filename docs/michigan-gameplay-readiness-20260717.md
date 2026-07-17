# Michigan Mitten Gameplay Readiness - 2026-07-17

## Installed baseline

- World: `MichiganMitten`, 40,960 m square.
- Terrain, road, building, and landmark PBOs are byte-identical on client and server.
- Physical roads are native WRP objects; the old mission-time road loader is disabled.
- Active server mission contains 43 intentional files and no persistence or test-backup artifacts.
- Previous mission and persistence are archived at `archives/pre-gameplay-ce-install-20260717-150749`.

## Central Economy population

- 4,399 Michigan building and landmark placements registered for loot.
- 119 reusable building prototypes with 881 prototype sockets.
- 34,167 placement-expanded loot sockets across the world.
- 388 infected territory zones.
- 116 wildlife territories, including deer, boar, fox, hare, wolves, and bears.
- 134 road-aligned land-vehicle spawn candidates.
- 24 water-verified boat spawn candidates.
- 28 land-verified helicopter crash candidates.
- Six fresh-player spawn bubbles centered on Hometown.

## Conservative first-test limits

- `ZombieMaxCount`: 420
- `AnimalMaxCount`: 120
- `InitialSpawn`: 80
- `SpawnInitial`: 900
- `ZoneSpawnDist`: 300 m

These limits are intentionally conservative for the first populated boot. They can be raised after the server log and in-game population are verified.

## First boot test

1. Start the server only through MI Server Manager.
2. Allow extra time for the first Central Economy database build.
3. Confirm the console reaches mission read, Steam policy response, player connection enabled, and idle/IN state without XML or CE errors.
4. Join and confirm the player spawns in Hometown.
5. Inspect several custom buildings for floor loot.
6. Inspect Hometown and a second city for infected.
7. Inspect a forest corridor for wildlife.
8. Inspect a road vehicle candidate and a shoreline boat candidate.
9. Verify roads, bridges, buildings, map tiles, and native terrain remain unchanged.

## Rollback

The complete previous mission, including its old `storage_1`, is preserved in the archive above. Stop the server, replace the active `dayzOffline.MichiganMitten` directory with the archived `dayzOffline.MichiganMitten.previous`, and restart through MI Server Manager.

## Verification status

Static CE validation: passed.

Installed mission validation: passed.

Deterministic CE regeneration: passed, 25 of 25 files matched byte-for-byte.

Combined terrain, road, map, package, gameplay, install, and client/server parity gate: `ready-for-live-test` with zero errors.

Live populated server boot: pending user-run test through MI Server Manager.
