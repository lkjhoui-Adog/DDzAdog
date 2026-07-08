class MichiganSurvivalSpawnObject
{
	string name;
	float pos[3];
	float ypr[3];
	float scale;
	bool enableCEPersistency;
}

class MichiganSurvivalSpawnData
{
	ref array<ref MichiganSurvivalSpawnObject> Objects;

	void MichiganSurvivalSpawnData()
	{
		Objects = new array<ref MichiganSurvivalSpawnObject>;
	}
}

void main()
{
	//INIT ECONOMY--------------------------------------
	Hive ce = CreateHive();
	if ( ce )
		ce.InitOffline();

	//DATE RESET AFTER ECONOMY INIT-------------------------
	int year, month, day, hour, minute;
	int reset_month = 9, reset_day = 20;
	GetGame().GetWorld().GetDate(year, month, day, hour, minute);

	if ((month == reset_month) && (day < reset_day))
	{
		GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
	}
	else
	{
		if ((month == reset_month + 1) && (day > reset_day))
		{
			GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
		}
		else
		{
			if ((month < reset_month) || (month > reset_month + 1))
			{
				GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
			}
		}
	}
}

class CustomMission: MissionServer
{
	protected bool m_MichiganSurvivalObjectsSpawned = false;

	override void OnMissionStart()
	{
		super.OnMissionStart();
		Print("[MichiganSurvival] Mission start reached; spawning object layer");
		PrintMichiganSurvivalSurfaceSamples();
		SpawnMichiganSurvivalObjects();
	}

	void PrintMichiganSurvivalSurfaceSample(string label, float x, float z)
	{
		vector position = Vector(x, GetGame().SurfaceY(x, z), z);
		PrintFormat("[MichiganSurvival] Surface sample %1 at %2", label, position.ToString(false));
	}

	void PrintMichiganSurvivalSurfaceSamples()
	{
		PrintMichiganSurvivalSurfaceSample("DowntownTraverseCity", 4666, 5083);
		PrintMichiganSurvivalSurfaceSample("TestPlaza", 6460, 4224);
		PrintMichiganSurvivalSurfaceSample("BoardmanLake", 5862, 2759);
		PrintMichiganSurvivalSurfaceSample("WestGrandTraverseBay", 2620, 8171);
		PrintMichiganSurvivalSurfaceSample("EastGrandTraverseBay", 9000, 7600);
	}

	bool IsMichiganSurvivalRoad(string type)
	{
		return type.Contains("rds_");
	}

	bool IsMichiganSurvivalWaterVisual(string type)
	{
		return type.Contains("pond") || type.Contains("stream") || type.Contains("water");
	}

	bool IsMichiganSurvivalSmallStatic(string type)
	{
		return type.Contains("Lamp_") || type.Contains("TrafficLights") || type.Contains("FuelStation_Sign");
	}

	bool IsMichiganSurvivalHouse(string type)
	{
		return type.Contains("house_");
	}

	float GetMichiganSurvivalFallbackYOffset(string type)
	{
		if (IsMichiganSurvivalRoad(type))
			return 0.05;

		if (IsMichiganSurvivalWaterVisual(type))
			return 0.02;

		if (IsMichiganSurvivalSmallStatic(type))
			return 1.0;

		if (type.Contains("airport"))
			return 3.0;

		if (type.Contains("Shed_Open"))
			return 1.75;

		if (type.Contains("BusStation"))
			return 0.75;

		return 1.5;
	}

	float GetMichiganSurvivalBaseClearance(string type)
	{
		if (type.Contains("FuelStation_Sign"))
			return 0.12;

		if (IsMichiganSurvivalSmallStatic(type))
			return 0.04;

		if (type.Contains("FuelStation_Shed"))
			return -0.85;

		if (type.Contains("airport_small_main"))
			return -1.55;

		if (type.Contains("airport_small_hangar"))
			return -0.95;

		if (type.Contains("house_1w02_blue"))
			return -1.45;

		if (IsMichiganSurvivalHouse(type))
			return -2.65;

		if (type.Contains("Shed_Open"))
			return -0.25;

		if (type.Contains("BusStation"))
			return 0.02;

		if (type.Contains("City_FireStation") || type.Contains("FuelStation_Shed") || type.Contains("mobilelaboratory") || type.Contains("radio_building"))
			return -0.2;

		return -0.25;
	}

	float GetMichiganSurvivalSurfaceSampleRadius(string type)
	{
		if (IsMichiganSurvivalSmallStatic(type))
			return 0.0;

		if (type.Contains("FuelStation_Shed"))
			return 10.0;

		if (type.Contains("City_FireStation"))
			return 9.0;

		if (type.Contains("airport_small_hangar"))
			return 12.0;

		if (type.Contains("airport_small_main"))
			return 10.0;

		if (IsMichiganSurvivalHouse(type))
			return 2.5;

		if (type.Contains("Shed_Open"))
			return 4.5;

		if (type.Contains("radio_building") || type.Contains("mobilelaboratory"))
			return 5.0;

		if (type.Contains("BusStation"))
			return 3.0;

		return 4.0;
	}

	float GetMichiganSurvivalPlacementSurfaceY(string type, float x, float z)
	{
		float radius = GetMichiganSurvivalSurfaceSampleRadius(type);
		float maxY = GetGame().SurfaceY(x, z);

		if (radius <= 0.01)
			return maxY;

		float halfRadius = radius * 0.5;
		float sampleY = GetGame().SurfaceY(x + radius, z);
		if (sampleY > maxY)
			maxY = sampleY;

		sampleY = GetGame().SurfaceY(x - radius, z);
		if (sampleY > maxY)
			maxY = sampleY;

		sampleY = GetGame().SurfaceY(x, z + radius);
		if (sampleY > maxY)
			maxY = sampleY;

		sampleY = GetGame().SurfaceY(x, z - radius);
		if (sampleY > maxY)
			maxY = sampleY;

		sampleY = GetGame().SurfaceY(x + halfRadius, z + halfRadius);
		if (sampleY > maxY)
			maxY = sampleY;

		sampleY = GetGame().SurfaceY(x - halfRadius, z + halfRadius);
		if (sampleY > maxY)
			maxY = sampleY;

		sampleY = GetGame().SurfaceY(x + halfRadius, z - halfRadius);
		if (sampleY > maxY)
			maxY = sampleY;

		sampleY = GetGame().SurfaceY(x - halfRadius, z - halfRadius);
		if (sampleY > maxY)
			maxY = sampleY;

		return maxY;
	}

	bool ShouldLogMichiganSurvivalSettle(string type, int debugCount)
	{
		if (debugCount < 48)
			return true;

		return type.Contains("FuelStation") || type.Contains("Lamp_") || type.Contains("TrafficLights") || type.Contains("FireStation") || type.Contains("mobilelaboratory") || type.Contains("radio_building") || type.Contains("airport_small_main") || type.Contains("airport_small_hangar") || type.Contains("house_1w01") || type.Contains("house_1w02_blue") || type.Contains("house_2w01") || type.Contains("BusStation_wall") || type.Contains("BusStation_roof_long");
	}

	bool ShouldSnapMichiganSurvivalBaseToSurface(string type)
	{
		return !IsMichiganSurvivalRoad(type) && !IsMichiganSurvivalWaterVisual(type);
	}

	void SpawnMichiganSurvivalObjects()
	{
		if (m_MichiganSurvivalObjectsSpawned)
			return;

		m_MichiganSurvivalObjectsSpawned = true;

		string filePath = "$mission:custom/MichiganSurvivalObjects.json";
		MichiganSurvivalSpawnData data = new MichiganSurvivalSpawnData();
		JsonFileLoader<MichiganSurvivalSpawnData>.JsonLoadFile(filePath, data);

		if (!data || !data.Objects || data.Objects.Count() == 0)
		{
			Print("[MichiganSurvival] Object layer not loaded from " + filePath);
			return;
		}

		int spawned = 0;
		int failed = 0;
		int debugStatics = 0;

		foreach (MichiganSurvivalSpawnObject item: data.Objects)
		{
			if (!item || item.name == "")
			{
				failed++;
				continue;
			}

			vector position = Vector(item.pos[0], 0, item.pos[2]);
			float surfaceY = GetGame().SurfaceY(position[0], position[2]);
			position[1] = surfaceY + GetMichiganSurvivalFallbackYOffset(item.name);

			float objectScale = item.scale;
			if (objectScale <= 0)
				objectScale = 1.0;

			Object obj = GetGame().CreateObjectEx(item.name, position, ECE_SETUP | ECE_UPDATEPATHGRAPH | ECE_CREATEPHYSICS | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD | ECE_NOPERSISTENCY_CHAR);
			if (!obj)
			{
				failed++;
				Print("[MichiganSurvival] Failed to spawn " + item.name);
				continue;
			}

			obj.SetPosition(position);
			obj.SetOrientation(Vector(item.ypr[0], item.ypr[1], item.ypr[2]));
			obj.SetScale(objectScale);
			obj.Update();

			if (ShouldSnapMichiganSurvivalBaseToSurface(item.name))
			{
				vector clipInfo[2];
				obj.ClippingInfo(clipInfo);
				float clipMinY = clipInfo[0][1];
				float baseClearance = GetMichiganSurvivalBaseClearance(item.name);
				float placementSurfaceY = GetMichiganSurvivalPlacementSurfaceY(item.name, position[0], position[2]);

				if (clipMinY < -0.02 && clipMinY > -20.0)
					position[1] = placementSurfaceY - clipMinY + baseClearance;
				else
					position[1] = placementSurfaceY + GetMichiganSurvivalFallbackYOffset(item.name);

				obj.SetPosition(position);
				obj.Update();

				if (ShouldLogMichiganSurvivalSettle(item.name, debugStatics))
				{
					PrintFormat("[MichiganSurvival] Static settle %1 centerSurface %2 placementSurface %3 clipMinY %4 clearance %5 final %6", item.name, surfaceY, placementSurfaceY, clipMinY, baseClearance, position.ToString(false));
					debugStatics++;
				}
			}

			obj.SetAffectPathgraph(true, false);
			if (obj.CanAffectPathgraph())
				GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(GetGame().UpdatePathgraphRegionByObject, 100, false, obj);

			spawned++;
			if (spawned <= 12)
				PrintFormat("[MichiganSurvival] Spawned %1 at %2", item.name, position.ToString(false));
		}

		PrintFormat("[MichiganSurvival] Object layer spawned %1 objects, failed %2", spawned, failed);
	}

	void SetRandomHealth(EntityAI itemEnt)
	{
		if ( itemEnt )
		{
			float rndHlt = Math.RandomFloat( 0.45, 0.65 );
			itemEnt.SetHealth01( "", "", rndHlt );
		}
	}

	override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
	{
		SpawnMichiganSurvivalObjects();

		Entity playerEnt;
		playerEnt = GetGame().CreatePlayer( identity, characterName, pos, 0, "NONE" );
		Class.CastTo( m_player, playerEnt );

		GetGame().SelectPlayer( identity, m_player );

		return m_player;
	}

	override void StartingEquipSetup(PlayerBase player, bool clothesChosen)
	{
		EntityAI itemClothing;
		EntityAI itemEnt;
		ItemBase itemBs;
		float rand;

		itemClothing = player.FindAttachmentBySlotName( "Body" );
		if ( itemClothing )
		{
			SetRandomHealth( itemClothing );
			
			itemEnt = itemClothing.GetInventory().CreateInInventory( "BandageDressing" );
			player.SetQuickBarEntityShortcut(itemEnt, 2);
			
			string chemlightArray[] = { "Chemlight_White", "Chemlight_Yellow", "Chemlight_Green", "Chemlight_Red" };
			int rndIndex = Math.RandomInt( 0, 4 );
			itemEnt = itemClothing.GetInventory().CreateInInventory( chemlightArray[rndIndex] );
			SetRandomHealth( itemEnt );
			player.SetQuickBarEntityShortcut(itemEnt, 1);

			rand = Math.RandomFloatInclusive( 0.0, 1.0 );
			if ( rand < 0.35 )
				itemEnt = player.GetInventory().CreateInInventory( "Apple" );
			else if ( rand > 0.65 )
				itemEnt = player.GetInventory().CreateInInventory( "Pear" );
			else
				itemEnt = player.GetInventory().CreateInInventory( "Plum" );
			player.SetQuickBarEntityShortcut(itemEnt, 3);
			SetRandomHealth( itemEnt );
		}
		
		itemClothing = player.FindAttachmentBySlotName( "Legs" );
		if ( itemClothing )
			SetRandomHealth( itemClothing );
		
		itemClothing = player.FindAttachmentBySlotName( "Feet" );
	}
};

Mission CreateCustomMission(string path)
{
	return new CustomMission();
}
