::g_DoorSeeds <- {};
::g_BackroomsSeedComputePending <- false;

function DebugLog(msg)
{
    printl("[Backrooms] " + msg);
}

function DumpParams(params)
{
    local out = "{ ";
    foreach (k, v in params)
        out += k + "=" + v + " ";
    out += "}";
    return out;
}

function HashString(str)
{
    local h = 5381;
    foreach (c in str)
        h = ((h * 33) + c) & 0x7fffffff;
    return h;
}

function MixSeed(tick, playerSeed, networkIDHash)
{
    local s = tick & 0x7fffffff;
    s = (s * 2654435761 + playerSeed) & 0x7fffffff;
    s = (s * 2654435761 + networkIDHash) & 0x7fffffff;
    return s;
}

function GenerateDoors(baseSeed)
{
    local rng = EngineRandom();
    rng.SetSeed(baseSeed);

    local doors = [];
    for (local i = 0; i < 10; i++)
        doors.append(rng.RandomInt(0, 9));
    return doors;
}

function ComputePlayerSeeds()
{
    g_DoorSeeds.clear();

    for (local i = 1; i <= MaxClients(); i++)
    {
        local p = PlayerInstanceFromIndex(i);
        if (p == null || !p.IsValid())
            continue;

        local netid = p.GetNetworkID();
        if (netid == "" || netid == "BOT")
            continue;

        local tick = NetProps.GetPropInt(p, "m_nSimulationTick");
        local playerSeed = p.GetRandomSeed();
        local networkIDHash = HashString(netid);
        local baseSeed = MixSeed(tick, playerSeed, networkIDHash);
        g_DoorSeeds[netid] <- baseSeed;

        local doors = GenerateDoors(baseSeed);
        local line = "";
        for (local lvl = 0; lvl < doors.len(); lvl++)
            line += "L" + lvl + "=" + doors[lvl] + " ";
        DebugLog(netid + "  doors: " + line);
    }
}

function ZeroPlayerSeed(netid)
{
    if (netid == null || netid == "" || netid == "BOT")
        return;

    if (netid in g_DoorSeeds)
    {
        g_DoorSeeds[netid] = null;
    }
}

::DebugLog <- DebugLog;
::DumpParams <- DumpParams;
::HashString <- HashString;
::MixSeed <- MixSeed;
::GenerateDoors <- GenerateDoors;
::ComputePlayerSeeds <- ComputePlayerSeeds;
::ZeroPlayerSeed <- ZeroPlayerSeed;

::Backrooms_RunSeedCompute <- function(reason)
{
    g_BackroomsSeedComputePending = false;

    ComputePlayerSeeds();
    BackroomsDoors.ResetRound();
}

::Backrooms_RequestSeedCompute <- function(reason)
{
    if (g_BackroomsSeedComputePending)
        return;

    g_BackroomsSeedComputePending = true;

    EntFireByHandle(
        self,
        "RunScriptCode",
        "Backrooms_RunSeedCompute(\"" + reason + "\")",
        0,
        null,
        null
    );
}

::GetCorrectDoor <- function(steamID, level)
{
    if (!(steamID in g_DoorSeeds))
        return -1;
    if (level < 0 || level > 9)
        return -1;

    local baseSeed = g_DoorSeeds[steamID];
    if (baseSeed == null)
        return -1;

    local rng = EngineRandom();
    rng.SetSeed(baseSeed);

    local correct = 0;
    for (local i = 0; i <= level; i++)
        correct = rng.RandomInt(0, 9);

    return correct;
}

::IsCorrectDoor <- function(steamID, level, door)
{
    if (door < 0 || door > 9)
        return false;

    return (door == GetCorrectDoor(steamID, level));
}

::BackroomsDoors <- {
    maxStage = 10,
    triggersPerStage = 10,
    triggerPrefix = "tg_stage",
    loseDestName = "lose_entry",

    function StageDestName(stage)
    {
        if (stage < 10)
            return "stage0" + stage.tostring() + "_entry";

        return "stage" + stage.tostring() + "_entry";
    },

    function NextDestName(stage)
    {
        if (stage >= maxStage)
            return "finish_entry";

        return StageDestName(stage + 1);
    },

    function ParseInteger(text)
    {
        if (text == null || text.len() <= 0)
            return null;

        try
        {
            return text.tointeger();
        }
        catch (e)
        {
        }

        return null;
    },

    function ParseTriggerName(name)
    {
        if (name == null)
            return null;

        local prefixAt = name.find(triggerPrefix);

        if (prefixAt == null || prefixAt != 0)
            return null;

        local rest = name.slice(triggerPrefix.len());
        local separatorAt = rest.find("_");

        if (separatorAt == null)
            return null;

        local stage = ParseInteger(rest.slice(0, separatorAt));
        local door = ParseInteger(rest.slice(separatorAt + 1));

        if (stage == null || door == null)
            return null;

        return {
            stage = stage,
            door = door
        };
    },

    function ResetRound()
    {
    },

    function GetPlayerSteamID(player)
    {
        local netid = player.GetNetworkID();

        if (netid == "" || netid == "BOT")
            return "";

        return netid;
    },

    function FindDestination(name)
    {
        return Entities.FindByName(null, name);
    },

    function FindDestinations(name)
    {
        local list = [];
        local ent = null;

        while ((ent = Entities.FindByName(ent, name)) != null)
        {
            list.append(ent);
        }

        return list;
    },

    function GetMapTick()
    {
        local root = getroottable();

        if (root.rawin("GetServerTick"))
            return root.GetServerTick();

        return (Time() * 66.0).tointeger();
    },

    function PickRandomDestination(name, stage, door)
    {
        local list = FindDestinations(name);

        if (list.len() <= 0)
            return null;

        local rng = EngineRandom();
        rng.SetSeed(MixSeed(GetMapTick(), stage * 100 + door, list.len()));

        return list[rng.RandomInt(0, list.len() - 1)];
    },

    function TeleportPlayerToDestination(player, dest)
    {
        if (dest == null)
            return;

        player.Teleport(
            true, dest.GetOrigin(),
            false, QAngle(0, 0, 0),
            true, Vector(0, 0, 0)
        );
    },

    function TeleportPlayer(player, destName)
    {
        TeleportPlayerToDestination(player, FindDestination(destName));
    },

    function Touched()
    {
        if (activator == null || !activator.IsPlayer())
            return;

        if (caller == null)
            return;

        local parsed = ParseTriggerName(caller.GetName());

        if (parsed == null)
            return;

        local stage = parsed.stage;
        local door = parsed.door;

        if (stage < 1 || stage > maxStage || door < 0 || door >= triggersPerStage)
            return;

        local steamID = GetPlayerSteamID(activator);
        local level = stage - 1;

        if (steamID != "" && IsCorrectDoor(steamID, level, door))
        {
            TeleportPlayer(activator, NextDestName(stage));
            return;
        }

        TeleportPlayerToDestination(activator, PickRandomDestination(loseDestName, stage, door));

        if (steamID != "")
        {
            local correct = GetCorrectDoor(steamID, level);
            if (correct >= 0)
                ClientPrint(activator, 2, "How unfortunate, you should've picked " + correct + ".");
        }
    }
};

function BackroomsDoors_Touch()
{
    BackroomsDoors.Touched();
}

function OnGameEvent_teamplay_round_start(params)
{
    Backrooms_RequestSeedCompute("teamplay_round_start");
}

function OnGameEvent_player_death(params)
{
    local player = GetPlayerFromUserID(params.userid);

    if (player == null || !player.IsValid())
        return;

    ZeroPlayerSeed(player.GetNetworkID());
}

function OnGameEvent_player_disconnect(params)
{
    if ("networkid" in params)
        ZeroPlayerSeed(params.networkid);

    local player = GetPlayerFromUserID(params.userid);

    if (player != null && player.IsValid())
        ZeroPlayerSeed(player.GetNetworkID());
}

__CollectGameEventCallbacks(this);

//EntFireByHandle(
//    self,
//    "RunScriptCode",
//    "Backrooms_RequestSeedCompute(\"map_load\")",
//    0,
//    null,
//    null
//);
