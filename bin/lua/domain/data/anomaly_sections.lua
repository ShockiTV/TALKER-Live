-- domain/data/anomaly_sections.lua
-- Set of known anomaly section names and section→display-name mapping.
-- Extracted from gamedata/configs/text/eng/talker_anomalies.xml.
-- Zero engine dependencies — pure data module.
--
-- Usage:
--   anomaly_sections.is_anomaly("zone_buzz_weak")   → true
--   anomaly_sections.describe("zone_vortex")         → "a Vortex anomaly (...)"
local M = {}

-- section_name → display_name
local SECTIONS = {
    -- Gas / Chemical anomalies
    ["zone_mine_acidic_weak"]               = "a Gas Anomaly (chemical cloud causing corrosive and toxic damage as well as choking).",
    ["zone_mine_acidic_average"]            = "a Gas Anomaly (chemical cloud causing corrosive and toxic damage as well as choking).",
    ["zone_mine_acidic_strong"]             = "a Gas Anomaly (chemical cloud causing corrosive and toxic damage as well as choking).",
    ["zone_mine_acidic_big"]                = "a Gas Anomaly (chemical cloud causing corrosive and toxic damage as well as choking).",
    ["zone_mine_chemical_weak"]             = "a Gas Anomaly (chemical cloud causing corrosive and toxic damage as well as choking).",
    ["zone_mine_chemical_average"]          = "a Gas Anomaly (chemical cloud causing corrosive and toxic damage as well as choking).",
    ["zone_mine_chemical_strong"]           = "a Gas Anomaly (chemical cloud causing corrosive and toxic damage as well as choking).",

    -- Electric / Electro anomalies
    ["zone_mine_electric_weak"]             = "an Electro anomaly (electrical field discharging lightning).",
    ["zone_mine_electric_average"]          = "an Electro anomaly (electrical field discharging lightning).",
    ["zone_mine_electric_strong"]           = "an Electro anomaly (electrical field discharging lightning).",
    ["zone_mine_static_weak"]               = "an Electro anomaly (electrical field discharging lightning).",
    ["zone_mine_static_average"]            = "an Electro anomaly (electrical field discharging lightning).",
    ["zone_mine_static_strong"]             = "an Electro anomaly (electrical field discharging lightning).",

    -- Gravitational anomalies
    ["zone_mine_gravitational_weak"]        = "a gravitational anomaly (spatial distortion).",
    ["zone_mine_gravitational_average"]     = "a gravitational anomaly (spatial distortion).",
    ["zone_mine_gravitational_strong"]      = "a gravitational anomaly (spatial distortion).",
    ["zone_mine_gravitational_big"]         = "a gravitational anomaly (spatial distortion).",
    ["zone_vortex"]                         = "a Vortex anomaly (gravitational whirlwind pulling objects inward).",
    ["zone_mine_vortex"]                    = "a Vortex anomaly (gravitational whirlwind pulling objects inward).",
    ["zone_gravi_zone"]                     = "a gravitational zone (area of spatial distortion).",

    -- Thermal anomalies
    ["zone_mine_thermal_weak"]              = "a Burner anomaly (thermal pillar of flame causing fire damage).",
    ["zone_mine_thermal_average"]           = "a Burner anomaly (thermal pillar of flame causing fire damage).",
    ["zone_mine_thermal_strong"]            = "a Burner anomaly (thermal pillar of flame causing fire damage).",
    ["zone_mine_steam_weak"]                = "a Steam anomaly (intense heat source causing thermal damage).",
    ["zone_mine_steam_average"]             = "a Steam anomaly (intense heat source causing thermal damage).",
    ["zone_mine_steam_strong"]              = "a Steam anomaly (intense heat source causing thermal damage).",
    ["zone_zharka_static_weak"]             = "a Zharka thermal anomaly (intense heat source).",
    ["zone_zharka_static_average"]          = "a Zharka thermal anomaly (intense heat source).",
    ["zone_zharka_static_strong"]           = "a Zharka thermal anomaly (intense heat source).",

    -- Buzz / Fruit Punch anomalies
    ["zone_buzz_weak"]                      = "a Fruit Punch anomaly (green corrosive puddle causing chemical damage).",
    ["zone_buzz_average"]                   = "a Fruit Punch anomaly (green corrosive puddle causing chemical damage).",
    ["zone_buzz_strong"]                    = "a Fruit Punch anomaly (green corrosive puddle causing chemical damage).",

    -- Toxic anomalies
    ["zone_witches_galantine_weak"]         = "a weak toxic anomaly.",
    ["zone_witches_galantine_average"]      = "a toxic anomaly.",
    ["zone_witches_galantine_strong"]       = "a very toxic anomaly.",

    -- Radioactive fields
    ["zone_field_radioactive"]              = "a radioactive field.",
    ["zone_field_radioactive_weak"]         = "a weakly radioactive field.",
    ["zone_field_radioactive_average"]      = "an averagely radioactive field.",
    ["zone_field_radioactive_strong"]       = "a strongly radioactive field.",
    ["zone_radioactive"]                    = "a radioactive zone.",
    ["zone_radioactive_weak"]               = "a weakly radioactive zone.",
    ["zone_radioactive_average"]            = "an averagely radioactive zone.",
    ["zone_radioactive_strong"]             = "a strongly radioactive zone.",

    -- Acidic fields
    ["zone_field_acidic"]                   = "an acidic field.",
    ["zone_field_acidic_weak"]              = "a weakly acidic field.",
    ["zone_field_acidic_average"]           = "an averagely acidic field.",
    ["zone_field_acidic_strong"]            = "a strongly acidic field.",

    -- Psychic fields
    ["zone_field_psychic"]                  = "a Psy-field (psychic interference causing mental damage. Prolonged unprotected exposure results in hallucinations and eventually zombification.).",
    ["zone_field_psychic_weak"]             = "a Psy-field (psychic interference causing mental damage. Prolonged unprotected exposure results in hallucinations and eventually zombification.).",
    ["zone_field_psychic_average"]          = "a Psy-field (psychic interference causing mental damage. Prolonged unprotected exposure results in hallucinations and eventually zombification.).",
    ["zone_field_psychic_strong"]           = "a Psy-field (psychic interference causing mental damage. Prolonged unprotected exposure results in hallucinations and eventually zombification.).",

    -- Thermal fields
    ["zone_field_thermal"]                  = "a thermal field.",
    ["zone_field_thermal_weak"]             = "a weakly thermal field.",
    ["zone_field_thermal_average"]          = "an averagely thermal field.",
    ["zone_field_thermal_strong"]           = "a strongly thermal field.",

    -- Radar / Brain Scorcher
    ["zone_mine_radar"]                     = "a Psy-field caused by the Brain Scorcher (psychic interference causing mental damage. Prolonged exposure without a psi-helmet results in hallucinations and eventually zombification.).",

    -- Space anomalies (Mosquito Bald)
    ["zone_mosquito_bald_weak"]             = "a Space anomaly (spatial distortion).",
    ["zone_mosquito_bald_average"]          = "a Space anomaly (spatial distortion).",
    ["zone_mosquito_bald_strong"]           = "a Space anomaly (spatial distortion).",

    -- Miscellaneous base-game anomalies
    ["zone_zhar"]                           = "a Comet anomaly (mobile fireball causing severe burn damage).",
    ["zone_liana"]                          = "a Pulse anomaly (pulsating energy field).",
    ["zone_teleport"]                       = "a Teleport anomaly (spatial distortion causing displacement).",
    ["zone_student"]                        = "a Burnt Fuzz anomaly (resembles moss or vines, hanging down like curtains. Relatively harmless, but can damage unarmored stalkers upon contact.).",
    ["zone_emi"]                            = "a Tesla anomaly (mobile ball of electricity).",

    -- Arrival mod
    ["zone_mine_cdf"]                       = "a Cognitive Dissonance Field anomaly (a highly localized breach in the fabric of the Noosphere, causing psychic damage).",
    ["zone_mine_umbra"]                     = "an Umbral Cluster anomaly (a swarm of shadow-like entities that move in unison, causing psychic damage).",
    ["zone_mine_flash"]                     = "a Flash anomaly (a tear in the space-time continuum that disrupts the fabric of the universe itself).",
    ["zone_mine_ghost"]                     = "a Ghost anomaly (a puff of smoky, ethereal substance. Touching it can lead to electrocution or disintegration).",
    ["zone_mine_gold"]                      = "a Liquid Gold anomaly (a cloud of golden orange colored toxic chemical substance).",
    ["zone_mine_thorn"]                     = "a Thorn anomaly (a small patch on the ground that rapidly expands into jagged spiky thorns in all directions).",
    ["zone_mine_seed"]                      = "a Seed anomaly (a highly radioactive cloud of tiny particles that multiply when agitated).",
    ["zone_mine_shatterpoint"]              = "a Shatterpoint anomaly (a cluster of glass-like shards tied to a central point and suspended in the air).",
    ["zone_mine_sloth"]                     = "a Sloth anomaly (a highly dangerous chemical anomaly).",
    ["zone_mine_mefistotel"]                = "a Mefistotel anomaly (a strange flower-like formation with delicate tendrils that pulls in and shreds anyone who approaches too closely).",
    ["zone_mine_net"]                       = "a Net anomaly (a cloud of charged particles trapping anyone that touches it).",
    ["zone_mine_point"]                     = "a Point anomaly (crystalline orb charged with electric energy).",
    ["zone_mine_sphere"]                    = "a Rebounder anomaly (a gravitational anomaly altering the trajectory of moving objects).",
}

--- Flat Set of all known anomaly section names for fast membership testing.
-- @type table<string, true>
M.ids = {}
for section, _ in pairs(SECTIONS) do
    M.ids[section] = true
end

--- Returns true if the section string is a known anomaly section.
-- @param section  Technical section name (e.g. "zone_buzz_weak"), may be nil
-- @return         true/false; never errors
function M.is_anomaly(section)
    if not section then return false end
    return M.ids[section] == true
end

--- Returns the human-readable display name for a known anomaly section.
-- @param section  Technical section name (e.g. "zone_vortex"), may be nil
-- @return         Display name string, or nil if not found
function M.describe(section)
    if not section then return nil end
    return SECTIONS[section]
end

--- The raw section→display-name table (exposed for tooling / tests).
M.sections = SECTIONS

return M
