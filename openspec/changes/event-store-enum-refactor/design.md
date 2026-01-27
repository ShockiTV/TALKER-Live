# Event Store Enum Refactor - Design

## EventType Enum

```lua
-- domain/model/event_types.lua

local EventType = {
  -- Combat
  DEATH = "death",                  -- context: {victim, killer?}
  CALLOUT = "callout",              -- context: {spotter, target}
  TAUNT = "taunt",                  -- context: {taunter, target}
  
  -- Items
  ARTIFACT = "artifact",            -- context: {actor, action, item_name, item_section?}
                                    -- action: "pickup"|"equip"|"use"|"unequip"
  
  -- World
  EMISSION = "emission",            -- context: {emission_type, status}
                                    -- emission_type: "emission"|"psi_storm"
                                    -- status: "starting"|"ending"
  MAP_TRANSITION = "map_transition", -- context: {actor, destination, source?}
  ANOMALY = "anomaly",              -- context: {actor, anomaly_type}
  
  -- Player State  
  INJURY = "injury",                -- context: {actor}
  SLEEP = "sleep",                  -- context: {actor, companions?}
  TASK = "task",                    -- context: {actor, action, task_name, task_giver?}
                                    -- action: "completed"|"failed"
  WEAPON_JAM = "weapon_jam",        -- context: {actor}
  RELOAD = "reload",                -- context: {actor}
  
  -- Dialogue
  DIALOGUE = "dialogue",            -- context: {speaker, text, source_event?}
  IDLE = "idle",                    -- context: {speaker, instruction?}
}

return EventType
```

## Event Model Changes

```lua
-- domain/model/event.lua

local EventType = require("domain.model.event_types")

local Event = {}
Event.TYPE = EventType  -- expose for external use

-- NEW: Typed event constructor
function Event.create(type, context, game_time_ms, world_context, witnesses, flags)
  return {
    type = type,
    context = context or {},
    game_time_ms = game_time_ms,
    world_context = world_context,
    witnesses = witnesses or {},
    flags = flags or {},
  }
end

-- DEPRECATED: Old constructor (keep temporarily for compatibility)
function Event.create_event(description, involved_objects, ...)
  -- existing implementation, marked for removal
end

-- NEW: Extract all characters referenced in context
function Event.get_involved_characters(event)
  local characters = {}
  local dominated_keys = {"victim", "killer", "actor", "spotter", "target", 
                          "taunter", "speaker", "companions"}
  
  for _, key in ipairs(dominated_keys) do
    local val = event.context[key]
    if val then
      if type(val) == "table" and val.game_id then
        table.insert(characters, val)
      elseif type(val) == "table" then
        -- companions array case
        for _, char in ipairs(val) do
          if char.game_id then
            table.insert(characters, char)
          end
        end
      end
    end
  end
  
  return characters
end
```

## Template Resolution

```lua
-- domain/model/event.lua (continued)

local TEMPLATES = {
  [EventType.DEATH] = function(ctx)
    if ctx.killer then
      return "%s was killed by %s!", {ctx.victim, ctx.killer}
    else
      return "%s died!", {ctx.victim}
    end
  end,
  
  [EventType.CALLOUT] = function(ctx)
    return "%s spotted %s!", {ctx.spotter, ctx.target}
  end,
  
  [EventType.TAUNT] = function(ctx)
    return "%s taunted %s!", {ctx.taunter, ctx.target}
  end,
  
  [EventType.ARTIFACT] = function(ctx)
    local verbs = {
      pickup = "picked up",
      equip = "equipped", 
      use = "used",
      unequip = "unequipped"
    }
    return "%s " .. verbs[ctx.action] .. " %s", {ctx.actor, ctx.item_name}
  end,
  
  [EventType.EMISSION] = function(ctx)
    local status_text = ctx.status == "starting" and "is starting" or "has ended"
    return "A %s %s!", {ctx.emission_type, status_text}
  end,
  
  [EventType.MAP_TRANSITION] = function(ctx)
    if ctx.source then
      return "%s traveled from %s to %s", {ctx.actor, ctx.source, ctx.destination}
    else
      return "%s arrived at %s", {ctx.actor, ctx.destination}
    end
  end,
  
  [EventType.ANOMALY] = function(ctx)
    return "%s encountered %s anomaly!", {ctx.actor, ctx.anomaly_type}
  end,
  
  [EventType.INJURY] = function(ctx)
    return "%s was critically injured!", {ctx.actor}
  end,
  
  [EventType.SLEEP] = function(ctx)
    if ctx.companions and #ctx.companions > 0 then
      return "%s and companions rested", {ctx.actor}
    else
      return "%s rested", {ctx.actor}
    end
  end,
  
  [EventType.TASK] = function(ctx)
    local verb = ctx.action == "completed" and "completed" or "failed"
    if ctx.task_giver then
      return "%s %s task '%s' for %s", {ctx.actor, verb, ctx.task_name, ctx.task_giver}
    else
      return "%s %s task '%s'", {ctx.actor, verb, ctx.task_name}
    end
  end,
  
  [EventType.WEAPON_JAM] = function(ctx)
    return "%s's weapon jammed!", {ctx.actor}
  end,
  
  [EventType.RELOAD] = function(ctx)
    return "%s reloaded their weapon", {ctx.actor}
  end,
  
  [EventType.DIALOGUE] = function(ctx)
    return "%s: '%s'", {ctx.speaker, ctx.text}
  end,
  
  [EventType.IDLE] = function(ctx)
    if ctx.instruction then
      return ctx.instruction, {}  -- raw instruction, no formatting
    else
      return "%s wants to chat", {ctx.speaker}
    end
  end,
}

-- Resolve a character to its display string
local function describe_character(char)
  if type(char) == "string" then
    return char
  elseif type(char) == "table" and char.name then
    return Character.describe(char)
  else
    return tostring(char)
  end
end

function Event.describe(event)
  -- Handle legacy events with description field
  if event.description and not event.type then
    return Event.describe_event(event)  -- old path
  end
  
  local template_fn = TEMPLATES[event.type]
  if not template_fn then
    return "[Unknown event: " .. tostring(event.type) .. "]"
  end
  
  local template, objects = template_fn(event.context)
  
  if #objects == 0 then
    return template
  end
  
  local descriptions = {}
  for _, obj in ipairs(objects) do
    table.insert(descriptions, describe_character(obj))
  end
  
  return string.format(template, unpack(descriptions))
end
```

## Flag Deprecation

Remove from triggers (type replaces them):
- `is_death` → `EventType.DEATH`
- `is_artifact` → `EventType.ARTIFACT`
- `is_emission` → `EventType.EMISSION`
- `is_map_transition` → `EventType.MAP_TRANSITION`
- `is_anomaly` → `EventType.ANOMALY`
- `is_injury` → `EventType.INJURY`
- `is_sleep` → `EventType.SLEEP`
- `is_task` → `EventType.TASK`
- `is_weapon_jam` → `EventType.WEAPON_JAM`
- `is_reload` → `EventType.RELOAD`
- `is_callout` → `EventType.CALLOUT`
- `is_taunt` → `EventType.TAUNT`
- `is_idle` → `EventType.IDLE`

Keep (behavioral):
- `is_silent` - controls whether event triggers dialogue
- `is_compressed` - marks compressed memory events
- `is_synthetic` - marks injected time gap events
- `important_death` - affects dialogue importance weighting

## Trigger Migration Example (weapon_jam)

```lua
-- BEFORE (talker_trigger_weapon_jam.script)
local unformatted_description = player_fmt .. "'s weapon jammed!"
trigger.talker_game_event(unformatted_description, player_vals, witnesses, true, 
    { is_weapon_jam = true, is_silent = is_silent })

-- AFTER
local Event = require("domain.model.event")
local event = Event.create(
    Event.TYPE.WEAPON_JAM,
    { actor = player },
    queries.get_game_time_ms(),
    game.describe_world(player),
    witnesses,
    { is_silent = is_silent }
)
trigger.talker_event(event, true)  -- new trigger interface
```

## Interface Changes

```lua
-- interface/trigger.lua

-- NEW: typed event trigger
function m.talker_event(event, important)
  c.SendScriptCallback("talker_event", event, important)
end

-- DEPRECATED: old interface (keep temporarily)
function m.talker_game_event(unformatted_description, event_objects, witnesses, important, flags)
  -- existing implementation
end
```

## Files to Modify

1. `bin/lua/domain/model/event_types.lua` (NEW)
2. `bin/lua/domain/model/event.lua` (MODIFY)
3. `bin/lua/interface/trigger.lua` (MODIFY)
4. `gamedata/scripts/talker_listener_game_event.script` (MODIFY)
5. All `gamedata/scripts/talker_trigger_*.script` files (MODIFY)
6. `bin/lua/infra/AI/prompt_builder.lua` (MODIFY - use Event.describe)
7. `bin/lua/infra/AI/transformations.lua` (MODIFY - type checks instead of flag checks)
