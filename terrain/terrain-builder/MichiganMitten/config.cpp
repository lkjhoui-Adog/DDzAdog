#define ReadOnlyVerified 3

class CfgPatches
{
    class MichiganMitten
    {
        units[] = {"MichiganMitten"};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Surfaces_Bliss", "DZ_Sounds_Effects", "DZ_Worlds_Chernarusplus_World", "DZ_Worlds_Enoch"};
    };
};

class CfgSoundShaders
{
    class BK18_Closure_SoundShader;
    class IZH18_Closure_SoundShader: BK18_Closure_SoundShader {};

    class Drowning_male_2_SoundVoice_Char_SoundShader;
    class UnderwaterBreathHold_male_2_SoundVoice_Char_SoundShader;
    class pushHeavyHeavy_female_1_motohelmet_SoundVoice_Char_SoundShader;

    class Drowning_male_2_gag_SoundVoice_Char_SoundShader: Drowning_male_2_SoundVoice_Char_SoundShader {};
    class UnderwaterBreathHold_male_2_gag_SoundVoice_Char_SoundShader: UnderwaterBreathHold_male_2_SoundVoice_Char_SoundShader {};
    class pushHeavy_female_1_motohelmet_SoundVoice_Char_SoundShader: pushHeavyHeavy_female_1_motohelmet_SoundVoice_Char_SoundShader {};
};

class CfgWorlds
{
    class DefaultWorld;
    class CAWorld;

    class MichiganMitten: CAWorld
    {
        access = ReadOnlyVerified;
        description = "Michigan Mitten 40.96km Detroit First Pass";
        worldName = "MichiganMitten\world\MichiganMitten.wrp";
        ceFiles = "DZ\worlds\chernarusplus\ce";
        class Navmesh
        {
            navmeshName = "\MichiganMitten\navmesh\navmesh.nm";
            filterIsolatedIslandsOnLoad = 1;
            visualiseOffset = 0;
            class GenParams
            {
                tileWidth = 50;
                cellSize1 = 0.25;
                cellSize2 = 0.1;
                cellSize3 = 0.1;
                filterIsolatedIslands = 1;
                seedPosition[] = {7500, 0, 7500};
                class Agent
                {
                    diameter = 0.60000002;
                    standHeight = 1.5;
                    crouchHeight = 1;
                    proneHeight = 0.5;
                    maxStepHeight = 0.44999999;
                    maxSlope = 60;
                };
                class Links
                {
                    class ZedJump387_050
                    {
                        jumpLength = 1.5;
                        jumpHeight = 0.5;
                        minCenterHeight = 0.30000001;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {"jumpOver"};
                        color = 1727987712;
                    };
                    class ZedJump388_050
                    {
                        jumpLength = 1.5;
                        jumpHeight = 0.5;
                        minCenterHeight = -0.5;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {"jumpOver"};
                        color = 1725781248;
                    };
                    class ZedJump387_110
                    {
                        jumpLength = 3.9000001;
                        jumpHeight = 1.1;
                        minCenterHeight = 0.5;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {"jumpOver"};
                        color = 1711308800;
                    };
                    class ZedJump420_160
                    {
                        jumpLength = 4;
                        jumpHeight = 1.6;
                        minCenterHeight = 1.1;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {"jumpOver"};
                        color = 1711276287;
                    };
                    class ZedJump265_210
                    {
                        jumpLength = 2.45;
                        jumpHeight = 2.5;
                        minCenterHeight = 1.8;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump0";
                        flags[] = {"climb"};
                        color = 1720975571;
                    };
                    class Fence50_110deer
                    {
                        typeId = 100;
                        jumpLength = 8;
                        jumpHeight = 1.1;
                        minCenterHeight = 0.5;
                        jumpDropdownMin = 1;
                        jumpDropdownMax = -1;
                        areaType = "jump2";
                        flags[] = {"jumpOver"};
                        color = 1722460927;
                    };
                    class Fence110_160deer
                    {
                        typeId = 101;
                        jumpLength = 8;
                        jumpHeight = 1.6;
                        minCenterHeight = 1.1;
                        jumpDropdownMin = 1;
                        jumpDropdownMax = -1;
                        areaType = "jump3";
                        flags[] = {"jumpOver"};
                        color = 1713700856;
                    };
                    class Fence50_110hen
                    {
                        typeId = 110;
                        jumpLength = 4;
                        jumpHeight = 1.1;
                        minCenterHeight = 0.5;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump4";
                        flags[] = {"jumpOver"};
                        color = -22016;
                    };
                    class Fence110_160hen
                    {
                        typeId = 111;
                        jumpLength = 4;
                        jumpHeight = 1.6;
                        minCenterHeight = 1.1;
                        jumpDropdownMin = 0.5;
                        jumpDropdownMax = -0.5;
                        areaType = "jump4";
                        flags[] = {"jumpOver"};
                        color = -22016;
                    };
                };
            };
        };
        mapSize = 40960;
        cutscenes[] = {};
        startTime = "12:00";
        startDate = "06/01/2026";
        startWeather = 0.35;
        startFog = 0.05;
        forecastWeather = 0.35;
        forecastFog = 0.05;
        centerPosition[] = {20480.000, 20480.000, 80};
        seagullPos[] = {20480.000, 20480.000, 120};
        ilsPosition[] = {20480.000, 20480.000};
        ilsDirection[] = {0.000, 0.080, -1.000};
        ilsTaxiIn[] = {20480.000, 20480.000};
        ilsTaxiOff[] = {20480.000, 20480.000};
        drawTaxiway = 0;
        longitude = -83.045800;
        latitude = 42.331400;
        mapDisplayNameKey = "Michigan Mitten";
        mapDescriptionKey = "Michigan Mitten";
        clutterGrid = 1.0;
        clutterDist = 125;
        noDetailDist = 65;
        fullDetailDist = 15;
        midDetailTexture = "DZ\surfaces_bliss\data\terrain\cp_grass_ca.paa";
        heightBlendingMode = 1;
        bicubicMode = 1;


		class Weather
		{
			class ThunderboltNorm
			{
				model = "\core\default\default.p3d";
				soundSetNear = "";
				soundSetFar = "";
				timeMultiplier = 1.2;
			};
			class ThunderboltHeavy
			{
				model = "\core\default\default.p3d";
				soundSetNear = "";
				soundSetFar = "";
				timeMultiplier = 1.5;
			};
			class Fog
			{
				nearDistanceFraction = 0.5;
				farDistanceFraction = 0.89999998;
			};
			class RainFog
			{
				distance = 350;
			};
			class SnowfallFog
			{
				distance = 350;
			};

			class Overcast
			{
				class Weather1
				{
					overcast=0.07;
					lightingOvercast=0;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather2
				{
					overcast=0.1;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage10_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather3
				{
					overcast=0.16;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage11_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather4
				{
					overcast=0.22;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage12_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather5
				{
					overcast=0.28;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage13_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather6
				{
					overcast=0.34;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.560784,0.572549,0.623529,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage14_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=1;
					godrayStrength=0.050000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather7
				{
					overcast=0.40000001;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\enoch\data\Sky_Stage10_Cirrus_en_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage15_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.80000001;
					godrayStrength=0.15000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather8
				{
					overcast=0.46000001;
					lightingOvercast=0.15000001;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\enoch\data\Sky_Stage10_Cirrus_en_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage16_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.64999998;
					godrayStrength=0.15000001;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather9
				{
					overcast=0.51999998;
					lightingOvercast=0.30000001;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					skyR="DZ\data\data\sky_clear_lco.paa";
					farCloud="DZ\worlds\enoch\data\Sky_Stage10_Cirrus_en_sky.paa";
					cloud="DZ\worlds\enoch\data\Cloud_Stage16_Cumulus_en_sky.paa";
					cloudClip=0.80000001;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage01_ClearHills_sky.paa";
					horizonClip=0.80000001;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.60000002;
					godrayStrength=0.1;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather10
				{
					overcast=0.57999998;
					lightingOvercast=0.57999998;
					sky="#(argb,8,8,3)color(0.45098,0.490196,0.611765,1.0,CO)";
					farCloud="DZ\worlds\chernarusplus\data\Cloud_Stage20_Altostratus_sky.paa";
					skyR="DZ\data\data\sky_semicloudy_lco.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage01_Transparent_sky.paa";
					cloudClip=0;
					horizon="DZ\worlds\chernarusplus\data\Horizont_Stage02_FoggyHills_sky.paa";
					horizonClip=0;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0.40000001;
					godrayStrength=0;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather11
				{
					overcast=0.77999997;
					lightingOvercast=1;
					sky="#(argb,8,8,3)color(0.141176,0.168627,0.215686,1.0,CO)";
					skyR="DZ\data\data\sky_mostlycloudy_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Sky_Stage30_Stratocumulus_sky.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage30_Nimbostratus_sky.paa";
					cloudClip=0;
					horizon="DZ\worlds\chernarusplus\data\Cloud_Stage00_Transparent_sky.paa";
					horizonClip=0;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0;
					godrayStrength=0;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
				class Weather12
				{
					overcast=1.01;
					lightingOvercast=1;
					sky="#(argb,8,8,3)color(0.141176,0.141176,0.141176,1.0,CO)";
					skyR="DZ\data\data\sky_mostlycloudy_lco.paa";
					farCloud="DZ\worlds\chernarusplus\data\Sky_Stage30_Stratocumulus_sky.paa";
					cloud="DZ\worlds\chernarusplus\data\Cloud_Stage31_Nimbostratus_sky.paa";
					cloudClip=0;
					horizon="DZ\worlds\chernarusplus\data\Cloud_Stage00_Transparent_sky.paa";
					horizonClip=0;
					alpha=0;
					bright=0;
					speed=0;
					size=0;
					height=0;
					through=0;
					godrayStrength=0;
					diffuse=0;
					cloudDiffuse=0;
					waves=0;
				};
			};
			class VolFog
			{
				CameraFog=0;
				Item1[]={500,0.059999999,0.93000001,0.13,1};
				Item2[]={1100,0.5,0.2,0.1,1};
				Item3[]={1300,0.0099999998,0.89999998,0.050000001,1};
				UseDynamic=1;
			};
		};
		volFogOffset=170;
		spaceObject="DZ\Data\data\milkyway.p3d";
		spaceObjectRotationPreOffset[]={0,0,0};
		spaceObjectRotationOffset[]={0,0,0};
		spaceTexture0="DZ\Data\data\milkyway_left_co.paa";
		spaceTexture1="DZ\Data\data\milkyway_right_co.paa";
		atmosphereObject="DZ\Data\data\atmosphere.p3d";
		atmosphereTexture="DZ\worlds\chernarusplus\data\Sky_Stage01_Clear_sky.paa";
		farCloudObject="DZ\Data\data\obloha.p3d";
		farCloudObjectRotationAxis[]={0,1,0};
		farCloudObjectRotationSpeed=3;
		nearCloudObject="DZ\Data\data\cloudObject.p3d";
		cloudObject="DZ\Data\data\cloudObject.p3d";
		cloudObjectRotationAxis[]={0,1,0};
		cloudObjectRotationSpeed=9;
		horizonObject="DZ\Data\data\horizont.p3d";
		horizonObjectRotationAxis[]={0,1,0};
		horizonObjectRotationSpeed=0;

        class UsedTerrainMaterials
        {
            material0 = "MichiganMitten\data\michigan_grass.rvmat";
            material1 = "MichiganMitten\data\michigan_forest.rvmat";
            material2 = "MichiganMitten\data\michigan_water.rvmat";
            material3 = "MichiganMitten\data\michigan_road.rvmat";
            material4 = "MichiganMitten\data\michigan_farmland.rvmat";
            material5 = "MichiganMitten\data\michigan_urban.rvmat";
        };

        class Names
        {
            class Detroit
            {
                name = "Detroit";
                position[] = {20480.000, 20480.000};
                type = "NameCityCapital";
                radiusA = 1400.000;
                radiusB = 1200.000;
                angle = 0.000;
            };
            class DowntownDetroit
            {
                name = "Downtown Detroit";
                position[] = {21400.000, 19100.000};
                type = "NameCity";
                radiusA = 550.000;
                radiusB = 450.000;
                angle = 0.000;
            };
            class DetroitRiver
            {
                name = "Detroit River";
                position[] = {23500.000, 16000.000};
                type = "NameMarine";
                radiusA = 1400.000;
                radiusB = 500.000;
                angle = 20.000;
            };
            class BelleIsle
            {
                name = "Belle Isle";
                position[] = {25000.000, 20000.000};
                type = "NameLocal";
                radiusA = 500.000;
                radiusB = 300.000;
                angle = 0.000;
            };
            class Dearborn
            {
                name = "Dearborn";
                position[] = {15000.000, 18500.000};
                type = "NameCity";
                radiusA = 650.000;
                radiusB = 550.000;
                angle = 0.000;
            };
            class Southfield
            {
                name = "Southfield";
                position[] = {12800.000, 27800.000};
                type = "NameCity";
                radiusA = 650.000;
                radiusB = 550.000;
                angle = 0.000;
            };
            class RoyalOak
            {
                name = "Royal Oak";
                position[] = {17600.000, 29600.000};
                type = "NameCity";
                radiusA = 550.000;
                radiusB = 450.000;
                angle = 0.000;
            };
            class Warren
            {
                name = "Warren";
                position[] = {23000.000, 30500.000};
                type = "NameCity";
                radiusA = 700.000;
                radiusB = 550.000;
                angle = 0.000;
            };
            class SterlingHeights
            {
                name = "Sterling Heights";
                position[] = {27500.000, 33500.000};
                type = "NameCity";
                radiusA = 700.000;
                radiusB = 550.000;
                angle = 0.000;
            };
            class LakeStClair
            {
                name = "Lake St. Clair";
                position[] = {36500.000, 30500.000};
                type = "NameMarine";
                radiusA = 1600.000;
                radiusB = 1200.000;
                angle = 0.000;
            };
            class Downriver
            {
                name = "Downriver";
                position[] = {17000.000, 8700.000};
                type = "NameLocal";
                radiusA = 850.000;
                radiusB = 650.000;
                angle = 0.000;
            };
        };
    };

    initWorld = "MichiganMitten";
    demoWorld = "MichiganMitten";
};

class CfgWorldList
{
    class MichiganMitten {};
};


