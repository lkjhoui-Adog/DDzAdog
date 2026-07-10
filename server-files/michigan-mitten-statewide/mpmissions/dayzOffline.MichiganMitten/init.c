class MichiganMittenSpawnObject
{
	string name;
	float pos[3];
	float ypr[3];
	float scale;
	bool enableCEPersistency;
}

class MichiganMittenSpawnData
{
	ref array<ref MichiganMittenSpawnObject> Objects;

	void MichiganMittenSpawnData()
	{
		Objects = new array<ref MichiganMittenSpawnObject>;
	}
}

void main()
{
	Hive ce = CreateHive();
	if (ce)
		ce.InitOffline();

	int year, month, day, hour, minute;
	int resetMonth = 9;
	int resetDay = 20;
	GetGame().GetWorld().GetDate(year, month, day, hour, minute);

	if ((month == resetMonth && day < resetDay) || (month == resetMonth + 1 && day > resetDay) || month < resetMonth || month > resetMonth + 1)
		GetGame().GetWorld().SetDate(year, resetMonth, resetDay, hour, minute);
}

class CustomMission: MissionServer
{
	protected ref MichiganMittenSpawnData m_MichiganMittenRoadData;
	protected int m_MichiganMittenRoadIndex;
	protected int m_MichiganMittenRoadSpawned;
	protected int m_MichiganMittenRoadFailed;
	protected int m_MichiganMittenRoadHeightAdjusted;
	protected float m_MichiganMittenRoadTotalLift;
	protected float m_MichiganMittenRoadMaxLift;
	protected bool m_MichiganMittenRoadLoadStarted;

	override void OnMissionStart()
	{
		super.OnMissionStart();
		Print("[MichiganMitten] Statewide road-only mission start reached");
		LoadMichiganMittenRoads();
	}

	bool IsMichiganMittenRoad(string type)
	{
		return type.Contains("rds_");
	}

	float GetMichiganMittenRoadSampleCenterY(float centerX, float centerZ, float forwardX, float forwardZ, float rightX, float rightZ, float longitudinalSlope, float forwardOffset, float rightOffset)
	{
		float sampleX = centerX + forwardX * forwardOffset + rightX * rightOffset;
		float sampleZ = centerZ + forwardZ * forwardOffset + rightZ * rightOffset;
		return GetGame().SurfaceY(sampleX, sampleZ) - forwardOffset * longitudinalSlope;
	}

	float GetMichiganMittenRoadPlacementY(MichiganMittenSpawnObject item, float objectScale)
	{
		float yawRadians = item.ypr[0] * 0.01745329252;
		float pitchRadians = item.ypr[1] * 0.01745329252;
		float forwardX = Math.Sin(yawRadians);
		float forwardZ = Math.Cos(yawRadians);
		float rightX = Math.Cos(yawRadians);
		float rightZ = -Math.Sin(yawRadians);
		float longitudinalSlope = Math.Tan(pitchRadians);
		float halfLength = 12.0 * objectScale;
		float halfWidth = 3.0 * objectScale;
		float requiredCenterY = GetGame().SurfaceY(item.pos[0], item.pos[2]);

		for (int forwardStep = -2; forwardStep <= 2; forwardStep++)
		{
			float forwardOffset = halfLength * forwardStep * 0.5;
			for (int rightStep = -1; rightStep <= 1; rightStep++)
			{
				float rightOffset = halfWidth * rightStep;
				float sampleCenterY = GetMichiganMittenRoadSampleCenterY(item.pos[0], item.pos[2], forwardX, forwardZ, rightX, rightZ, longitudinalSlope, forwardOffset, rightOffset);
				if (sampleCenterY > requiredCenterY)
					requiredCenterY = sampleCenterY;
			}
		}

		return requiredCenterY + 0.045;
	}

	void LoadMichiganMittenRoads()
	{
		if (m_MichiganMittenRoadLoadStarted)
			return;

		m_MichiganMittenRoadLoadStarted = true;
		m_MichiganMittenRoadData = new MichiganMittenSpawnData();
		string filePath = "$mission:custom/MichiganMittenObjects.json";
		JsonFileLoader<MichiganMittenSpawnData>.JsonLoadFile(filePath, m_MichiganMittenRoadData);

		if (!m_MichiganMittenRoadData || !m_MichiganMittenRoadData.Objects || m_MichiganMittenRoadData.Objects.Count() == 0)
		{
			Print("[MichiganMitten] Road layer not loaded from " + filePath);
			return;
		}

		PrintFormat("[MichiganMitten] Loaded %1 road records; beginning batched placement", m_MichiganMittenRoadData.Objects.Count());
		GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(SpawnMichiganMittenRoadBatch, 100, false);
	}

	void SpawnMichiganMittenRoadBatch()
	{
		if (!m_MichiganMittenRoadData || !m_MichiganMittenRoadData.Objects)
			return;

		int objectCount = m_MichiganMittenRoadData.Objects.Count();
		int batchEnd = m_MichiganMittenRoadIndex + 160;
		if (batchEnd > objectCount)
			batchEnd = objectCount;

		for (; m_MichiganMittenRoadIndex < batchEnd; m_MichiganMittenRoadIndex++)
		{
			MichiganMittenSpawnObject item = m_MichiganMittenRoadData.Objects[m_MichiganMittenRoadIndex];
			if (!item || item.name == "" || !IsMichiganMittenRoad(item.name))
			{
				m_MichiganMittenRoadFailed++;
				continue;
			}

			float objectScale = item.scale;
			if (objectScale <= 0)
				objectScale = 1.0;

			vector position = Vector(item.pos[0], 0, item.pos[2]);
			float centerOnlyY = GetGame().SurfaceY(position[0], position[2]) + 0.045;
			position[1] = GetMichiganMittenRoadPlacementY(item, objectScale);
			float heightLift = position[1] - centerOnlyY;
			if (heightLift > 0.005)
			{
				m_MichiganMittenRoadHeightAdjusted++;
				m_MichiganMittenRoadTotalLift += heightLift;
				if (heightLift > m_MichiganMittenRoadMaxLift)
					m_MichiganMittenRoadMaxLift = heightLift;
			}

			Object road = GetGame().CreateObjectEx(item.name, position, ECE_SETUP | ECE_CREATEPHYSICS | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD | ECE_NOPERSISTENCY_CHAR);
			if (!road)
			{
				m_MichiganMittenRoadFailed++;
				continue;
			}

			road.SetPosition(position);
			road.SetOrientation(Vector(item.ypr[0], item.ypr[1], item.ypr[2]));
			road.SetScale(objectScale);
			road.Update();
			m_MichiganMittenRoadSpawned++;
		}

		if (m_MichiganMittenRoadIndex < objectCount)
		{
			if ((m_MichiganMittenRoadIndex % 1600) == 0)
				PrintFormat("[MichiganMitten] Road placement progress %1/%2", m_MichiganMittenRoadIndex, objectCount);

			GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(SpawnMichiganMittenRoadBatch, 50, false);
			return;
		}

		PrintFormat("[MichiganMitten] Road layer complete: spawned %1, failed %2", m_MichiganMittenRoadSpawned, m_MichiganMittenRoadFailed);
		PrintFormat("[MichiganMitten] Road height alignment: adjusted %1, total lift %2 m, maximum lift %3 m", m_MichiganMittenRoadHeightAdjusted, m_MichiganMittenRoadTotalLift, m_MichiganMittenRoadMaxLift);
	}

	vector GetHometownSpawn(int choice)
	{
		switch (choice)
		{
			case 0: return Vector(32001.296, 0, 9973.177);
			case 1: return Vector(32181.296, 0, 10473.177);
			case 2: return Vector(32361.296, 0, 9893.177);
			case 3: return Vector(32551.296, 0, 10423.177);
			case 4: return Vector(32711.296, 0, 10093.177);
		}

		return Vector(32781.296, 0, 10513.177);
	}

	vector GetMichiganMittenCharacterSpawn(vector requestedPos)
	{
		vector spawnPos = requestedPos;
		bool invalid = spawnPos[0] < 1 || spawnPos[0] > 40959 || spawnPos[2] < 1 || spawnPos[2] > 40959;
		if (!invalid && GetGame().SurfaceY(spawnPos[0], spawnPos[2]) <= 0.5)
			invalid = true;

		if (invalid)
		{
			spawnPos = GetHometownSpawn(Math.RandomInt(0, 6));
			PrintFormat("[MichiganMitten] Invalid CE spawn redirected to Hometown: %1", spawnPos.ToString(false));
		}

		spawnPos[1] = GetGame().SurfaceY(spawnPos[0], spawnPos[2]) + 0.5;
		return spawnPos;
	}

	override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
	{
		vector spawnPos = GetMichiganMittenCharacterSpawn(pos);
		Entity playerEnt = GetGame().CreatePlayer(identity, characterName, spawnPos, 0, "NONE");
		Class.CastTo(m_player, playerEnt);
		GetGame().SelectPlayer(identity, m_player);
		return m_player;
	}

	void SetRandomHealth(EntityAI itemEnt)
	{
		if (itemEnt)
			itemEnt.SetHealth01("", "", Math.RandomFloat(0.45, 0.65));
	}

	override void StartingEquipSetup(PlayerBase player, bool clothesChosen)
	{
		EntityAI itemClothing;
		EntityAI itemEnt;
		float randomValue;

		itemClothing = player.FindAttachmentBySlotName("Body");
		if (itemClothing)
		{
			SetRandomHealth(itemClothing);
			itemEnt = itemClothing.GetInventory().CreateInInventory("BandageDressing");
			player.SetQuickBarEntityShortcut(itemEnt, 2);

			string chemlights[] = {"Chemlight_White", "Chemlight_Yellow", "Chemlight_Green", "Chemlight_Red"};
			itemEnt = itemClothing.GetInventory().CreateInInventory(chemlights[Math.RandomInt(0, 4)]);
			SetRandomHealth(itemEnt);
			player.SetQuickBarEntityShortcut(itemEnt, 1);

			randomValue = Math.RandomFloatInclusive(0.0, 1.0);
			if (randomValue < 0.35)
				itemEnt = player.GetInventory().CreateInInventory("Apple");
			else if (randomValue > 0.65)
				itemEnt = player.GetInventory().CreateInInventory("Pear");
			else
				itemEnt = player.GetInventory().CreateInInventory("Plum");

			player.SetQuickBarEntityShortcut(itemEnt, 3);
			SetRandomHealth(itemEnt);
		}

		itemClothing = player.FindAttachmentBySlotName("Legs");
		if (itemClothing)
			SetRandomHealth(itemClothing);

		itemClothing = player.FindAttachmentBySlotName("Feet");
		if (itemClothing)
			SetRandomHealth(itemClothing);
	}
}

Mission CreateCustomMission(string path)
{
	return new CustomMission();
}
