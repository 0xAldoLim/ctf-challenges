function SetConvars()
{
    Convars.SetValue("mp_autoteambalance", 0);
    Convars.SetValue("mp_teams_unbalance_limit", 0);
    Convars.SetValue("mp_scrambleteams_auto", 0);
    Convars.SetValue("mp_scrambleteams_auto_windifference", 0);
    Convars.SetValue("mp_waitingforplayers_cancel", 1)
    Convars.SetValue("mp_enableroundwaittime", 0)
    Convars.SetValue("tf_avoidteammates_pushaway", 0)

    Convars.SetValue("mp_humans_must_join_team", "red");

    Convars.SetValue("mp_disable_respawn_times", 0);

    Convars.SetValue("mp_respawnwavetime", 999999);

    Convars.SetValue("mp_forcecamera", 0);
    Convars.SetValue("tf_classlimit", 0);
}

::g_BackroomsDeathrunRoundActive <- false;
::g_BackroomsDeathrunRoundStartedAt <- 0.0;
::g_BackroomsDeathrunRoundEnding <- false;

function CountAliveRedPlayers()
{
    local alive = 0;

    for (local i = 1; i <= MaxClients(); i++)
    {
        local player = PlayerInstanceFromIndex(i);

        if (player == null || !player.IsValid())
            continue;

        if (NetProps.GetPropInt(player, "m_iTeamNum") != 2)
            continue;

        if (NetProps.GetPropInt(player, "m_lifeState") == 0)
            alive++;
    }

    return alive;
}

function CheckRoundEnd()
{
    if (!g_BackroomsDeathrunRoundActive || g_BackroomsDeathrunRoundEnding)
        return;

    if (Time() - g_BackroomsDeathrunRoundStartedAt < 2.0)
        return;

    local alive = CountAliveRedPlayers();

    if (alive <= 0)
    {
        g_BackroomsDeathrunRoundEnding = true;
        g_BackroomsDeathrunRoundActive = false;
        FireRoundWin();
    }
}

function FireRoundWin()
{
    local roundWin = null;

    while ((roundWin = Entities.FindByName(roundWin, "round_win")) != null)
        EntFireByHandle(roundWin, "RoundWin", "", 0.0, null, null);
}

function DelayedCheckRoundEnd(delay)
{
    EntFireByHandle(self, "RunScriptCode", "CheckRoundEnd()", delay, null, null);
}

function StartDeathrunRound()
{
    g_BackroomsDeathrunRoundActive = true;
    g_BackroomsDeathrunRoundEnding = false;
    g_BackroomsDeathrunRoundStartedAt = Time();

    EntFireByHandle(self, "RunScriptCode", "CheckRoundEnd()", 2.0, null, null);
}

SetConvars();

::DEATHRUN_BASE_MELEE <- [
    "tf_weapon_fists",
    "tf_weapon_bat",
    "tf_weapon_club",
    "tf_weapon_shovel",
    "tf_weapon_bottle",
    "tf_weapon_bonesaw",
    "tf_weapon_fists",
    "tf_weapon_fireaxe",
    "tf_weapon_knife",
    "tf_weapon_wrench",
];

::DEATHRUN_BASE_MELEE_INDEX <- [
    5,
    0,
    3,
    6,
    1,
    8,
    5,
    2,
    4,
    7,
];

const DEATHRUN_MAX_WEAPON_SLOTS = 8;

::DeathrunForceMelee <- function(player)
{
    if (player == null || !player.IsValid() || !player.IsPlayer())
        return;
    if (player.GetTeam() < 2)
        return;

    for (local i = 0; i < DEATHRUN_MAX_WEAPON_SLOTS; i++)
    {
        local weapon = NetProps.GetPropEntityArray(player, "m_hMyWeapons", i);
        if (weapon == null || !weapon.IsValid())
            continue;
        NetProps.SetPropEntityArray(player, "m_hMyWeapons", null, i);
        weapon.Kill();
    }

    local classIndex = player.GetPlayerClass();
    local classname = DEATHRUN_BASE_MELEE[classIndex];
    local itemIndex = DEATHRUN_BASE_MELEE_INDEX[classIndex];

    local melee = SpawnEntityFromTable(classname, {
        origin = player.GetOrigin(),
        angles = player.GetAbsAngles(),
        effects = 129,
    });
    if (melee == null || !melee.IsValid())
        return;

    NetProps.SetPropInt(melee, "m_AttributeManager.m_Item.m_iItemDefinitionIndex", itemIndex);
    NetProps.SetPropBool(melee, "m_bValidatedAttachedEntity", true);
    NetProps.SetPropBool(melee, "m_AttributeManager.m_Item.m_bInitialized", true);
    NetProps.SetPropInt(melee, "m_AttributeManager.m_iReapplyProvisionParity", 1);
    NetProps.SetPropBool(melee, "m_AttributeManager.m_Item.m_bOnlyIterateItemViewAttributes", true);
    melee.SetTeam(player.GetTeam());
    melee.DispatchSpawn();
    player.Weapon_Equip(melee);
    melee.ReapplyProvision();
    player.Weapon_Switch(melee);
}

function OnGameEvent_teamplay_round_start(params)
{
    SetConvars();
    StartDeathrunRound();
}

function OnGameEvent_teamplay_restart_round(params)
{
    SetConvars();
    StartDeathrunRound();
}

function OnGameEvent_player_death(params)
{
    DelayedCheckRoundEnd(0.1);
}

function OnGameEvent_player_disconnect(params)
{
    DelayedCheckRoundEnd(0.5);
}

function OnGameEvent_post_inventory_application(params)
{
    if (!("userid" in params))
        return;

    local player = GetPlayerFromUserID(params.userid);
    if (player == null)
        return;

    EntFireByHandle(player, "RunScriptCode", "::DeathrunForceMelee(self)", 0.1, null, null);
}

__CollectGameEventCallbacks(this);
