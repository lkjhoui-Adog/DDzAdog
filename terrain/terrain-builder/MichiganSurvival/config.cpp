#define ReadOnlyVerified 3

class CfgPatches
{
    class MichiganSurvival
    {
        units[] = {"MichiganSurvival"};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Surfaces_Bliss"};
    };
};

class CfgWorlds
{
    class DefaultWorld;
    class CAWorld: DefaultWorld {};

    class MichiganSurvival: CAWorld
    {
        access = ReadOnlyVerified;
        description = "Michigan Survival";
        worldName = "MichiganSurvival\world\MichiganSurvival.wrp";
        mapSize = 10000;
        cutscenes[] = {};
        startTime = "12:00";
        startDate = "06/01/2026";
        startWeather = 0.35;
        startFog = 0.05;
        forecastWeather = 0.35;
        forecastFog = 0.05;
        centerPosition[] = {5000, 5000, 80};
        seagullPos[] = {5000, 5000, 120};
        longitude = -85;
        latitude = 44;
        clutterGrid = 1.0;
        clutterDist = 125;
        noDetailDist = 65;
        fullDetailDist = 15;
        midDetailTexture = "DZ\surfaces_bliss\data\terrain\cp_grass_ca.paa";
        heightBlendingMode = 1;
        bicubicMode = 1;

        class UsedTerrainMaterials
        {
            material0 = "MichiganSurvival\data\michigan_grass.rvmat";
            material1 = "MichiganSurvival\data\michigan_forest.rvmat";
            material2 = "MichiganSurvival\data\michigan_water.rvmat";
            material3 = "MichiganSurvival\data\michigan_road.rvmat";
            material4 = "MichiganSurvival\data\michigan_farmland.rvmat";
            material5 = "MichiganSurvival\data\michigan_urban.rvmat";
        };

        class Names
        {
            class TraverseCity
            {
                name = "Traverse City";
                position[] = {5000, 5000};
                type = "NameCityCapital";
                radiusA = 650;
                radiusB = 650;
                angle = 0;
            };
            class DowntownTraverseCity
            {
                name = "Downtown Traverse City";
                position[] = {4666, 5083};
                type = "NameCity";
                radiusA = 300;
                radiusB = 300;
                angle = 0;
            };
            class GrandTraverseBay
            {
                name = "Grand Traverse Bay";
                position[] = {8132, 9710};
                type = "NameMarine";
                radiusA = 1000;
                radiusB = 750;
                angle = 0;
            };
            class WestGrandTraverseBay
            {
                name = "West Grand Traverse Bay";
                position[] = {2620, 8171};
                type = "NameMarine";
                radiusA = 900;
                radiusB = 650;
                angle = 0;
            };
            class EastGrandTraverseBay
            {
                name = "East Grand Traverse Bay";
                position[] = {9000, 7600};
                type = "NameMarine";
                radiusA = 900;
                radiusB = 650;
                angle = 0;
            };
            class BoardmanLake
            {
                name = "Boardman Lake";
                position[] = {5862, 2759};
                type = "NameMarine";
                radiusA = 360;
                radiusB = 520;
                angle = 0;
            };
            class BoardmanRiver
            {
                name = "Boardman River";
                position[] = {4552, 3870};
                type = "NameLocal";
                radiusA = 300;
                radiusB = 300;
                angle = 0;
            };
            class CherryCapitalAirport
            {
                name = "Cherry Capital Airport";
                position[] = {8081, 2653};
                type = "NameLocal";
                radiusA = 500;
                radiusB = 350;
                angle = 0;
            };
            class GarfieldTownship
            {
                name = "Garfield Township";
                position[] = {1886, 4715};
                type = "NameVillage";
                radiusA = 500;
                radiusB = 400;
                angle = 0;
            };
        };
    };

    initWorld = "MichiganSurvival";
    demoWorld = "MichiganSurvival";
};

class CfgWorldList
{
    class MichiganSurvival {};
};
