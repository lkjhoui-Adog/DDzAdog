void main()
{
}

class CustomMission: MissionServer
{
	override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
	{
		vector spawnPos = Vector(32361.296, 0, 10213.177);
		spawnPos[1] = GetGame().SurfaceY(spawnPos[0], spawnPos[2]) + 0.5;
		Entity playerEnt = GetGame().CreatePlayer(identity, characterName, spawnPos, 0, "NONE");
		Class.CastTo(m_player, playerEnt);
		GetGame().SelectPlayer(identity, m_player);
		return m_player;
	}

	override void StartingEquipSetup(PlayerBase player, bool clothesChosen)
	{
		player.RemoveAllItems();
	}
}

Mission CreateCustomMission(string path)
{
	return new CustomMission();
}
