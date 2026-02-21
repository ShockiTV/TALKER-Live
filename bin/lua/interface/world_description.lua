-- interface/world_description.lua
-- Pure string-assembly functions for world context descriptions.
-- Extracted from the describe_* functions in talker_game_queries.script.
-- Zero engine dependencies — all environment data is passed as parameters.
-- The engine data fetching (level.rain_factor(), etc.) stays in the script.
local M = {}

--- Maps an integer hour (0-23) to a time-of-day description.
-- @param hour  Integer hour
-- @return      "night" | "morning" | "noon" | "evening"
function M.time_of_day(hour)
    if hour < 6  then return "night"   end
    if hour < 10 then return "morning" end
    if hour < 15 then return "noon"    end
    if hour < 20 then return "evening" end
    return "night"
end

--- Returns an emission/psi-storm description string from boolean flags.
-- @param is_psy_storm  boolean
-- @param is_surge      boolean
-- @return              "" | "ongoing psy storm" | "ongoing emission"
function M.describe_emission(is_psy_storm, is_surge)
    if is_psy_storm then return "ongoing psy storm" end
    if is_surge     then return "ongoing emission"  end
    return ""
end

--- Normalizes a weather string and overrides with active emission if present.
-- @param weather_string    Raw weather name from engine (e.g. "partly", "clear")
-- @param emission_string   Return value of describe_emission() (may be "" or nil)
-- @return                  Human-readable weather description
function M.describe_weather(weather_string, emission_string)
    local weather = weather_string or ""
    if weather == "partly" then
        weather = "partially cloudy"
    end
    if emission_string and emission_string ~= "" then
        return "an " .. emission_string
    end
    return weather
end

--- Returns a shelter-status string based on rain conditions.
-- Does NOT call any engine APIs — both factors are pre-resolved by the caller.
-- The caller also decides whether to invoke this (e.g. whether the player is
-- indoors at all).
-- @param rain_factor    level.rain_factor()  (0–1)
-- @param rain_exposure  level.rain_hemi()    (0–1; low = sheltered)
-- @return               "and sheltering inside" | ""
function M.describe_shelter(rain_factor, rain_exposure)
    if rain_factor and rain_factor > 0.2
    and rain_exposure and rain_exposure < 0.1 then
        return "and sheltering inside"
    end
    return ""
end

--- Assembles the complete world description string from pre-resolved parameters.
-- Template (no campfire, no shelter):
--   "In {location} at {time_of_day} during {weather} weather."
-- With shelter:
--   "In {location} at {time_of_day} {shelter} during {weather} weather."
-- With campfire:
--   "In {location} at {time_of_day} during {weather} weather, next to a {lit|unlit} campfire."
--
-- @param params  table:
--   location    (string)  Display location name
--   time_of_day (string)  Return value of M.time_of_day()
--   weather     (string)  Return value of M.describe_weather()
--   shelter     (string)  Return value of M.describe_shelter() (may be "" or nil)
--   campfire    (string)  "lit" | "unlit" | nil
-- @return  Formatted world description string
function M.build_description(params)
    local location  = params.location    or "Unknown"
    local time_str  = params.time_of_day or "day"
    local weather   = params.weather     or "clear"
    local shelter   = params.shelter     or ""
    local campfire  = params.campfire

    -- Replace full stops in location names with commas (e.g. "Rostok. 100 Rads Bar")
    location = string.gsub(location, "%.", ",")

    -- Append a trailing space to shelter text when non-empty so spacing works in template
    local shelter_part = shelter ~= "" and (shelter .. " ") or ""

    -- Campfire context
    local campfire_context = ""
    if campfire == "lit" then
        campfire_context = ", next to a lit campfire"
    elseif campfire == "unlit" then
        campfire_context = ", next to an unlit campfire"
    end

    return string.format("In %s at %s %sduring %s weather%s.",
        location, time_str, shelter_part, weather, campfire_context)
end

return M
