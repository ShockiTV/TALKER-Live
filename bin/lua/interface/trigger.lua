local log = require("framework.logger")

local c = talker_game_commands

local m = {}

function m.talker_player_speaks(dialogue)
	log.debug("Calling trigger talker_player_speaks with arg: %s", dialogue)
	c.SendScriptCallback("talker_player_speaks", dialogue)
end

function m.talker_player_whispers(dialogue)
	log.debug("Calling trigger talker_player_whispers with arg: %s", dialogue)
	c.SendScriptCallback("talker_player_whispers", dialogue)
end

function m.talker_game_event(unformatted_description, event_objects, witnesses, important, flags)
	c.SendScriptCallback("talker_game_event", unformatted_description, event_objects, witnesses, important, flags)
end

function m.talker_game_event_near_player(unformatted_description, involved_objects, important, flags)
	c.SendScriptCallback("talker_game_event_near_player", unformatted_description, involved_objects, important, flags)
end

function m.talker_character_instructions(unformatted_description, character, important, flags)
	c.SendScriptCallback("talker_game_event_near_player", unformatted_description, { character }, important, flags)
	return true
end

function m.talker_silent_event_near_player(unformatted_description, involved_objects, flags)
	c.SendScriptCallback("talker_silent_event_near_player", unformatted_description, involved_objects, flags)
end

function m.talker_silent_event(unformatted_description, event_objects, witnesses, flags)
	c.SendScriptCallback("talker_silent_event", unformatted_description, event_objects, witnesses, flags)
end

return m
