# Michigan Mitten checkpoint - 2026-07-10

## Validated live build

- World: `dayzOffline.MichiganMitten`, statewide 40.96 km Lower Peninsula layout.
- Hometown is the primary spawn region near `32361.296, 10213.177`.
- The mission loaded 14,153 road panels with zero spawn failures.
- The real statewide navmesh generated successfully from the Hometown seed.
- Navmesh size: 301,537,868 bytes.
- Navmesh SHA-256: `BC3FA402EBDF1E7DECBE7E3533D8C73BE23E1658CB1B7CF23F2E4E996BBF512A`.
- Installed PBO size: 324,728,728 bytes.
- Installed PBO SHA-256: `EABE6CB846051876F617F66408E7FC7891616F8396E6512110994966330D3372`.
- Server booted through MI Server Manager, opened ports 2302, 2304, 2306, and 27016, and accepted a live client connection at Hometown without a navmesh error.
- The server was shut down cleanly through MI Server Manager at the end of this checkpoint.

## Road height alignment work in progress

- The validated live server still uses the center-height road placement from the previous checkpoint.
- `server-files/michigan-mitten-statewide/mpmissions/dayzOffline.MichiganMitten/init.c` contains an uninstalled work-in-progress footprint sampler.
- The sampler checks a rotated 25 m by 6 m footprint and records total/maximum lift.
- Do not deploy that work-in-progress sampler unchanged. Offline validation found that a highest-corner-only correction could lift a few panels as much as 8.516 m on sharp terrain.
- Resume by fitting panel pitch and roll to the sampled terrain plane, limiting residual vertical correction, and running the offline distribution check again before installing it.

## Generated artifacts kept locally

The signed PBO, WRP, ASC heightmap, PAA layers, and `.nm` navmesh remain on this machine. They are generated artifacts and may exceed GitHub's normal per-file limit, so the Git checkpoint records their source files, hashes, and reconstruction tools instead of attempting to upload the large binaries.
