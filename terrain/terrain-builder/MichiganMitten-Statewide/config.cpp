#define ReadOnlyVerified 3

class CfgPatches
{
    class MichiganMitten
    {
        units[] = {"MichiganMitten"};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Surfaces_Bliss", "DZ_Worlds_Chernarusplus_World", "DZ_Worlds_Enoch"};
    };
};

class CfgWorlds
{
    class DefaultWorld;
    class CAWorld;

    class MichiganMitten: CAWorld
    {
        access = ReadOnlyVerified;
        description = "Michigan Lower Peninsula 40.96km";
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
                seedPosition[] = {32361.296, 0, 10213.177};
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
        longitude = -84.650000;
        latitude = 43.760000;
        clutterGrid = 1.0;
        clutterDist = 125;
        noDetailDist = 65;
        fullDetailDist = 15;
        midDetailTexture = "DZ\surfaces_bliss\data\terrain\cp_grass_ca.paa";
        heightBlendingMode = 1;
        bicubicMode = 1;


		class Weather
		{
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
            class Hometown
            {
                name = "Hometown";
                position[] = {32361.296, 10213.177};
                type = "NameCityCapital";
                radiusA = 900.000;
                radiusB = 700.000;
                angle = 0.000;
            };
            class Detroit
            {
                name = "Detroit";
                position[] = {31655.214, 7153.735};
                type = "NameCityCapital";
                radiusA = 420.000;
                radiusB = 320.000;
                angle = 0.000;
            };
            class AnnArbor
            {
                name = "Ann Arbor";
                position[] = {26747.989, 6519.057};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Flint
            {
                name = "Flint";
                position[] = {26946.614, 13490.120};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Lansing
            {
                name = "Lansing";
                position[] = {20933.078, 10688.485};
                type = "NameCityCapital";
                radiusA = 420.000;
                radiusB = 320.000;
                angle = 0.000;
            };
            class GrandRapids
            {
                name = "Grand Rapids";
                position[] = {13118.906, 12800.611};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Kalamazoo
            {
                name = "Kalamazoo";
                position[] = {13718.243, 6411.120};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class BattleCreek
            {
                name = "Battle Creek";
                position[] = {16594.360, 6714.229};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Jackson
            {
                name = "Jackson";
                position[] = {22104.228, 6079.062};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Muskegon
            {
                name = "Muskegon";
                position[] = {9069.695, 15374.848};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Holland
            {
                name = "Holland";
                position[] = {10036.173, 11121.434};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class BentonHarbor
            {
                name = "Benton Harbor";
                position[] = {7583.854, 4743.933};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class PortHuron
            {
                name = "Port Huron";
                position[] = {35777.066, 13405.772};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Monroe
            {
                name = "Monroe";
                position[] = {29294.643, 3124.341};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Saginaw
            {
                name = "Saginaw";
                position[] = {25012.542, 17314.113};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class BayCity
            {
                name = "Bay City";
                position[] = {25399.311, 18990.012};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Midland
            {
                name = "Midland";
                position[] = {22917.140, 19132.765};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class MountPleasant
            {
                name = "Mount Pleasant";
                position[] = {19322.459, 18898.096};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class BigRapids
            {
                name = "Big Rapids";
                position[] = {14362.827, 19799.639};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Cadillac
            {
                name = "Cadillac";
                position[] = {14893.657, 25074.482};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Ludington
            {
                name = "Ludington";
                position[] = {7685.084, 22244.342};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Manistee
            {
                name = "Manistee";
                position[] = {8577.976, 24992.138};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class TraverseCity
            {
                name = "Traverse City";
                position[] = {13369.883, 29931.428};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Alpena
            {
                name = "Alpena";
                position[] = {28116.567, 33041.861};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Gaylord
            {
                name = "Gaylord";
                position[] = {19742.917, 32515.495};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Grayling
            {
                name = "Grayling";
                position[] = {19527.977, 29026.290};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class Petoskey
            {
                name = "Petoskey";
                position[] = {17806.854, 35779.785};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
                angle = 0.000;
            };
            class MackinawCity
            {
                name = "Mackinaw City";
                position[] = {19272.545, 39649.966};
                type = "NameCity";
                radiusA = 300.000;
                radiusB = 220.000;
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
