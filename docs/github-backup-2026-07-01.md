# GitHub Backup Snapshot - 2026-07-01

This snapshot is intended to preserve the DayZ Michigan Survival work without committing huge generated terrain/source files or third-party Workshop mod payloads directly to Git.

## Custom Map State

- Terrain/project workspace: `workdrive/MichiganSurvival`
- Built client/server mod: `build/@MichiganSurvival`
- PBO source tree: `build/pbo-src/MichiganSurvival`
- Current exported world: `workdrive/MichiganSurvival/world/MichiganSurvival.wrp`
- Current packed PBO: `build/@MichiganSurvival/Addons/MichiganSurvival.pbo`

Large raw and generated terrain artifacts are intentionally ignored in Git. The restore-critical large files are captured in the local GitHub backup archive under `backups/`.

## Adog Server State

The Adog server was updated for the Michigan Survival terrain and mod-sync work. The current server config, launch shortcut, launcher local-mod registration, and hash manifests are copied under `server-files/adog-current/`.

Important runtime facts from the latest known-good server boot:

- Server root: `C:\Users\Adog\Documents\MI-Server-Manager-2026.05.21.1455\servers\Adog`
- Server map/world: `MichiganSurvival`
- Server-side custom mod: `@MichiganSurvival`
- Launcher local mod fix: DayZ Launcher `Local.json` and default preset include `@MichiganSurvival`
- Expansion/Dabs mismatched PBOs were resynced from the client install; the full third-party mods are not copied into this Git repo.

## What Git Should Hold

- Planning docs and tool scripts
- Reproducible source/download/process scripts
- Lightweight QGIS/project config files
- Current server config snapshots and manifests
- Notes describing exact external files and hashes

## What Git Should Not Hold

- Full DayZ server install
- Full Workshop mod folders
- Raw USGS DEMs and generated raster exports
- Terrain Builder cache files and bulky intermediate terrain data
- Packed `.pbo`, `.wrp`, `.pew`, `.v4d`, and similar binary outputs unless they are intentionally attached as release assets

