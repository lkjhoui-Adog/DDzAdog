@echo off
set "DAYZ_ROOT=C:\Program Files (x86)\Steam\steamapps\common\DayZ"
set "MODS=%DAYZ_ROOT%\!Workshop\@CF;%DAYZ_ROOT%\!Workshop\@Community-Online-Tools;%DAYZ_ROOT%\!Workshop\@Dabs Framework;%DAYZ_ROOT%\!Workshop\@DayZ-Expansion-Licensed;%DAYZ_ROOT%\!Workshop\@DayZ-Expansion-Bundle;%DAYZ_ROOT%\!Workshop\@BuilderItems;%DAYZ_ROOT%\!Workshop\@DayZ-Editor;%DAYZ_ROOT%\!Workshop\@DayZ Editor Loader;%DAYZ_ROOT%\!Workshop\@MMG - Mightys Military Gear;%DAYZ_ROOT%\!Workshop\@DDz Gear Pack;%DAYZ_ROOT%\!Workshop\@TeddysWeaponPack;%DAYZ_ROOT%\@MichiganSurvival"

cd /d "%DAYZ_ROOT%"
start "" "%DAYZ_ROOT%\DayZ_BE.exe" 0 1 1 -exe DayZ_x64.exe -name=-DDz-AdogASC "-mod=%MODS%" -connect=192.168.12.246:2302:27016
