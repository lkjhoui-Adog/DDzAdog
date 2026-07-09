# Michigan Mitten Checkpoint - 2026-07-09

## Server Test State

- Terrain class: `MichiganMitten`
- Server profile: `C:\Users\Adog\AppData\Local\MI Server Manager\servers\Traverse City, MI`
- Active mission: `dayzOffline.MichiganMitten`
- Active mod folder installed by package script:
  - Client: `C:\Program Files (x86)\Steam\steamapps\common\DayZ\@MichiganMitten`
  - Server: `C:\Users\Adog\AppData\Local\MI Server Manager\servers\Traverse City, MI\@MichiganMitten`

## Large Local Artifacts

These are intentionally not committed to GitHub because normal GitHub git pushes reject large files and the repo ignores generated build/workdrive artifacts.

- Generated 2048 navmesh source:
  - `C:\DayZNavmesh\MichiganMitten2048.generated.nm`
  - Size: `1,843,853,088` bytes
- Active workdrive navmesh:
  - `workdrive\MichiganMitten\navmesh\navmesh.nm`
  - SHA256: `B8CE4F948A85EEAA6EE0F30E1D85B8F14E1063F50EEF8F9A1313759801FDA4E1`
- Packaged PBO installed to client/server:
  - `build\@MichiganMitten\Addons\MichiganMitten.pbo`
  - Size: `1,874,462,604` bytes
  - SHA256: `509706F5CD5379D06643A3DBE524B275980F13AB0867CB8180D57F44E07B5228`

## Last Test Result

The server launched through MI Server Manager with the restored 2048 WRP and matching 2048 navmesh. It passed landscape load and reached `Player connect enabled`, then accepted the player login.

The remaining blocker is a native crash during player creation:

- RPT: `profiles\DayZServer_x64_2026-07-09_15-12-48.RPT`
- Preload position: `7460.000000 0.000000 7410.000000`
- Crash line: `ENGINE (F): Crashed`
- Stack: `scripts/5_Mission/mission\missionserver.c:489 Function CreateCharacter`

This means the previous `cannot load navmesh` / read-mission issue was resolved by the real navmesh pass, but spawning a character on the custom terrain still needs the next debugging step.

## Next Suggested Step

Force the mission spawn path to set the player position to a real surface Y before `CreateCharacter`, then retest through MI Server Manager with a fresh `storage_1` backup.
