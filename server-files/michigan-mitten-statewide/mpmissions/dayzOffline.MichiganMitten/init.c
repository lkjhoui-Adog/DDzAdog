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
	override void OnMissionStart()
	{
		super.OnMissionStart();
		Print("[MichiganMitten] Native terrain roads active");
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
