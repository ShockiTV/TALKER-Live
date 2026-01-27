-- EventType enum definitions
-- Maps event categories to string identifiers for typed event storage

local EventType = {
	-- Combat
	DEATH = "death", -- context: {victim, killer?}
	CALLOUT = "callout", -- context: {spotter, target}
	TAUNT = "taunt", -- context: {taunter, target}

	-- Items
	ARTIFACT = "artifact", -- context: {actor, action, item_name, item_section?}
	-- action: "pickup"|"equip"|"use"|"unequip"

	-- World
	EMISSION = "emission", -- context: {emission_type, status}
	-- emission_type: "emission"|"psi_storm"
	-- status: "starting"|"ending"
	MAP_TRANSITION = "map_transition", -- context: {actor, destination, source?}
	ANOMALY = "anomaly", -- context: {actor, anomaly_type}

	-- Player State
	INJURY = "injury", -- context: {actor}
	SLEEP = "sleep", -- context: {actor, companions?}
	TASK = "task", -- context: {actor, action, task_name, task_giver?}
	-- action: "completed"|"failed"
	WEAPON_JAM = "weapon_jam", -- context: {actor}
	RELOAD = "reload", -- context: {actor}

	-- Dialogue
	DIALOGUE = "dialogue", -- context: {speaker, text, source_event?}
	IDLE = "idle", -- context: {speaker, instruction?}
}

return EventType
