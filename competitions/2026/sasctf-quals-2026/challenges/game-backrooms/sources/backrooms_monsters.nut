::BackroomsMonsters <- {
    tickRate = 66.0,
    thinkInterval = 0.10,
    spawnChancePerThink = 500,
    chanceScale = 10000,

    trainSpeed = 375,
    activeTicks = 540,
    lockTicks = 760,
    maxStartsPerThink = 1,

    trains = [],
    lanes = [],
    initialized = false,

    function TwoDigits(n)
    {
        if (n < 10)
            return "0" + n;

        return n.tostring();
    },

    function MakeTrain(id, group, train, visual, hurt)
    {
        return {
            id = id,
            group = group,
            train = train,
            visual = visual,
            hurt = hurt,
            active = false,
            activeUntil = 0,
            cooldownUntil = 0,
            lane = -1
        };
    },

    function MakeLane(id, group, start)
    {
        return {
            id = id,
            group = group,
            start = start,
            busy = false
        };
    },

    function BuildSlots()
    {
        trains = [];
        lanes = [];

        for (local i = 1; i <= 15; i++)
        {
            local id = "x" + TwoDigits(i);
            trains.append(MakeTrain(id, "x", "monster_train_" + id, "monster_visual_" + id, "monster_hurt_" + id));
            lanes.append(MakeLane(id, "x", "monster_path_" + id + "_start"));
        }

        for (local i = 1; i <= 15; i++)
        {
            local id = "y" + TwoDigits(i);
            trains.append(MakeTrain(id, "y", "monster_train_" + id, "monster_visual_" + id, "monster_hurt_" + id));
            lanes.append(MakeLane(id, "y", "monster_path_" + id + "_start"));
        }

        trains.append(MakeTrain("prototype", "p", "nexbot_train", "nexbot_visual", "nexbot_hurt"));
        lanes.append(MakeLane("prototype", "p", "path_nextbot1"));
    },

    function FindByName(name)
    {
        if (name == "")
            return null;

        return Entities.FindByName(null, name);
    },

    function TrainExists(t)
    {
        return FindByName(t.train) != null;
    },

    function LaneExists(lane)
    {
        return FindByName(lane.start) != null;
    },

    function SetNamedEnabled(name, enabled)
    {
        if (name == "")
            return;

        local ent = FindByName(name);

        if (ent == null)
            return;

        EntFireByHandle(ent, enabled ? "Enable" : "Disable", "", 0.00, null, null);
    },

    function StopTrain(t)
    {
        local train = FindByName(t.train);

        if (train != null)
            EntFireByHandle(train, "Stop", "", 0.00, null, null);

        SetNamedEnabled(t.visual, false);
        SetNamedEnabled(t.hurt, false);
        t.active = false;

        if (t.lane >= 0 && t.lane < lanes.len())
            lanes[t.lane].busy = false;

        t.lane = -1;
    },

    function GetMapTick()
    {
        local root = getroottable();

        if (root.rawin("GetServerTick"))
            return root.GetServerTick();

        return (Time() * tickRate).tointeger();
    },

    function Mix(value)
    {
        local x = value & 0x7fffffff;
        x = (x ^ (x >> 13)) & 0x7fffffff;
        x = (x * 1103515245 + 12345) & 0x7fffffff;
        x = (x ^ (x >> 16)) & 0x7fffffff;
        return x;
    },

    function Roll(tick, salt)
    {
        return Mix(tick + salt) % chanceScale;
    },

    function PickFreeLane(group, tick, salt)
    {
        local n = lanes.len();

        if (n <= 0)
            return -1;

        local first = Mix(tick + salt + 313) % n;

        for (local offset = 0; offset < n; offset++)
        {
            local index = (first + offset) % n;
            local lane = lanes[index];

            if (lane.group != group)
                continue;

            if (lane.busy)
                continue;

            if (!LaneExists(lane))
                continue;

            return index;
        }

        return -1;
    },

    function StartTrain(t, laneIndex, tick)
    {
        local train = FindByName(t.train);

        if (train == null)
            return false;

        local lane = lanes[laneIndex];

        if (!LaneExists(lane))
            return false;

        EntFireByHandle(train, "Stop", "", 0.00, null, null);
        EntFireByHandle(train, "TeleportToPathTrack", lane.start, 0.01, null, null);

        SetNamedEnabled(t.visual, true);
        SetNamedEnabled(t.hurt, true);

        EntFireByHandle(train, "StartForward", "", 0.04, null, null);

        t.active = true;
        t.activeUntil = tick + activeTicks;
        t.cooldownUntil = tick + lockTicks;
        t.lane = laneIndex;
        lane.busy = true;

        return true;
    },

    function ResetSlots()
    {
        foreach (t in trains)
        {
            t.cooldownUntil = 0;
            t.activeUntil = 0;
            StopTrain(t);
        }

        foreach (lane in lanes)
            lane.busy = false;
    },

    function Init()
    {
        BuildSlots();
        ResetSlots();
        initialized = true;
    },

    function Think()
    {
        if (!initialized)
            Init();

        local tick = GetMapTick();
        local started = 0;

        foreach (t in trains)
        {
            if (t.active && tick >= t.activeUntil)
                StopTrain(t);
        }

        local n = trains.len();

        if (n <= 0)
            return thinkInterval;

        local first = Mix(tick + 7717) % n;

        for (local offset = 0; offset < n; offset++)
        {
            local index = (first + offset) % n;
            local t = trains[index];

            if (t.active)
                continue;

            if (tick < t.cooldownUntil)
                continue;

            if (!TrainExists(t))
                continue;

            local roll = Roll(tick, index * 997);

            if (roll >= spawnChancePerThink)
                continue;

            local laneIndex = PickFreeLane(t.group, tick, index * 997);

            if (laneIndex < 0)
                continue;

            if (StartTrain(t, laneIndex, tick))
            {
                started++;

                if (started >= maxStartsPerThink)
                    break;
            }
        }

        return thinkInterval;
    }
};

function BackroomsMonsters_Think()
{
    return BackroomsMonsters.Think();
}

function OnGameEvent_teamplay_round_start(params)
{
    BackroomsMonsters.Init();
}

function OnGameEvent_teamplay_restart_round(params)
{
    BackroomsMonsters.Init();
}

BackroomsMonsters.Init();
__CollectGameEventCallbacks(this);
AddThinkToEnt(self, "BackroomsMonsters_Think");
