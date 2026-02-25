package.path = package.path .. ";./bin/lua/?.lua;"

-- Character class definition
Character = {}

function Character.new(game_id, name, experience, faction, reputation, weapon, visual_faction, story_id, sound_prefix)
	new_char = {
		game_id = game_id,
		name = name,
		experience = experience,
		faction = faction,
		reputation = reputation,
		weapon = weapon,
		visual_faction = visual_faction,
		story_id = story_id,
		sound_prefix = sound_prefix,
	}
	return new_char
end

return Character
