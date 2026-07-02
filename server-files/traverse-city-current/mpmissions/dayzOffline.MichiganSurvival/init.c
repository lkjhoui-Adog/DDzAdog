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

	float GetMichiganSurvivalFallbackYOffset(string type)
	{
		if (IsMichiganSurvivalRoad(type))
			return 0.05;

		if (IsMichiganSurvivalWaterVisual(type))
			return 0.02;

		if (IsMichiganSurvivalSmallStatic(type))
			return 0.25;

		if (type.Contains("airport"))
			return 3.0;

		if (type.Contains("Shed_Open"))
			return 1.75;

		if (type.Contains("BusStation"))
			return 0.75;

		return 1.5;
	}

	bool ShouldSnapMichiganSurvivalBaseToSurface(string type)
	{
		return !IsMichiganSurvivalRoad(type) && !IsMichiganSurvivalWaterVisual(type) && !IsMichiganSurvivalSmallStatic(type);
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

				if (clipMinY < -0.02 && clipMinY > -20.0)
					position[1] = surfaceY - clipMinY + 0.08;
				else
					position[1] = surfaceY + GetMichiganSurvivalFallbackYOffset(item.name);

				obj.SetPosition(position);
				obj.Update();

				if (debugStatics < 16)
				{
					PrintFormat("[MichiganSurvival] Static height %1 surface %2 clipMinY %3 final %4", item.name, surfaceY, clipMinY, position.ToString(false));
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
