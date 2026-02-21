package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")
local luaunit = require('tests.utils.luaunit')
local assert_or_record = require("tests.utils.assert_or_record")
package.path = package.path .. ';./gamedata/scripts/?.script'

----------------------------------------------------------------------------------------------------
-- Mocks
----------------------------------------------------------------------------------------------------

local interface = {
    register_game_event = function(unformatted_description, event_objects, witnesses)
        local event_data = {
            unformatted_description, event_objects, witnesses
        }
        assert_or_record('triggers', 'testTriggerReload', event_data)
    end
}

-- Override bootstrap's talker_game_queries with test-specific stubs
talker_game_queries.get_game_time_ms = function() return 0 end
talker_game_queries.is_living_character = function(obj) return true end
talker_game_queries.is_in_combat = function(npc) return false end
talker_game_queries.are_enemies = function(a, b) return false end
talker_game_queries.get_distance_between = function(a, b) return 10 end

require('talker_trigger_callout')

----------------------------------------------------------------------------------------------------
-- Test event on player reload
----------------------------------------------------------------------------------------------------

function testTriggerCallout()
    on_enemy_eval()
end



os.exit(luaunit.LuaUnit.run())