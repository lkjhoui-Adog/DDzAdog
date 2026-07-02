# Traverse City, MI server snapshot

Snapshot date: 2026-07-02

Live server folder:

`C:\Users\Adog\AppData\Local\MI Server Manager\servers\Traverse City, MI`

Updated manager folder:

`C:\Users\Adog\AppData\Local\MI Server Manager`

## Startup fix

The updated Server Manager copied the Michigan mission and `@MichiganSurvival` folder, but `mods.json` did not include MichiganSurvival. The manager started DayZ with the mission template set to `dayzOffline.MichiganSurvival` while omitting `@MichiganSurvival` from `-mod=`, which caused the map/world load failure.

Fixed in `mods.json`:

`MichiganSurvival` is enabled as a client mod with `FolderName` set to `MichiganSurvival` and `LoadOrder` set to `12`.

Verified launch line includes:

`-mod=@CF;@Community-Online-Tools;@Dabs Framework;@DayZ-Expansion-Licensed;@DayZ-Expansion-Bundle;@BuilderItems;@DayZ-Editor;@DayZ Editor Loader;@MMG - Mightys Military Gear;@DDz Gear Pack;@TeddysWeaponPack;@MichiganSurvival`

## Verified files

- `serverDZ.cfg` uses `template="dayzOffline.MichiganSurvival";`
- `config.json` points at `C:\Users\Adog\AppData\Local\MI Server Manager\servers\Traverse City, MI`
- `keys\MichiganSurvival.bikey` exists in the live server root
- `@MichiganSurvival\Addons\MichiganSurvival.pbo` exists in the live server mod folder
- `mpmissions\dayzOffline.MichiganSurvival\custom\MichiganSurvivalObjects.json` contains 1141 objects
- `init.c` includes the terrain-snap static height fix using `ClippingInfo`
- `init.c` also applies per-category ground clearances so roads stay flat, lamps/signs snap by their base, and houses/sheds sit slightly into the terrain instead of floating above it

## Runtime proof

Fresh logs from the fixed start:

- RPT: `profiles\DayZServer_x64_2026-07-02_16-36-54.RPT`
- Script: `profiles\script_2026-07-02_16-36-59.log`

Observed:

- DayZ reached `Player connect enabled`
- Mission script loaded from `mpmissions\dayzOffline.MichiganSurvival\init.c`
- `[MichiganSurvival] Mission start reached; spawning object layer`
- `[MichiganSurvival] Object layer spawned 1141 objects, failed 0`

## PBO sync

The live server PBO and local client PBO matched:

`5878AF24B9092380068CD704DE4C01C703933DAF07E596919655112998AE4FFB`

Checked paths:

- `C:\Users\Adog\AppData\Local\MI Server Manager\servers\Traverse City, MI\@MichiganSurvival\Addons\MichiganSurvival.pbo`
- `C:\Program Files (x86)\Steam\steamapps\common\DayZ\@MichiganSurvival\Addons\MichiganSurvival.pbo`

The PBO itself is intentionally not committed because `.pbo` files are ignored as build output.
