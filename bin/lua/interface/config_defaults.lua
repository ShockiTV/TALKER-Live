-- config_defaults.lua — MCM default values as a pure Lua table (no engine dependencies)
-- Single source of truth for all MCM defaults.
-- Used by interface/config.lua as fallback and by tests/mocks/mock_engine.lua.
local defaults = {
    -- Model settings
    gpt_version             = "gpt-4o",
    ai_model_method         = 3,
    custom_ai_model         = "gemini/gemini-2.5-flash",
    custom_ai_model_fast    = "gemini/gemini-2.5-flash-lite",
    reasoning_level         = -1,
    voice_provider          = 2,

    -- Language / locale
    language                = "Any",

    -- Input
    input_option            = "0",
    speak_key               = "x",
    whisper_modifier        = "0",

    -- Gameplay
    action_descriptions     = false,
    female_gender           = false,
    witness_distance        = 25,
    npc_speak_distance      = 30,
    time_gap                = 4,

    -- WebSocket / service
    service_type            = 0,
    service_hub_url         = "",
    branch                  = 0,
    custom_branch           = "",
    service_url             = "",
    service_ws_port         = 5557,
    ws_token                = "",
    auth_client_id          = "talker-client",
    auth_client_secret      = "",
    auth_username           = "",
    auth_password           = "",
    llm_timeout             = 60,
    state_query_timeout     = 10,

    -- TTS
    tts_volume_boost        = 8.0,

    -- Debug
    debug_logging           = 2,
    max_log_entries_per_level = 0,

    -- Speaker picker
    speaker_pick_max_events = 20,

    -- Save management
    reset_backstory         = false,
    reset_personality       = false,

    -- General trigger settings
    recent_speech_threshold = 120,
    anti_spam_cd            = 10,

    -- Per-trigger settings: triggers/<type>/<setting>
    -- Death (player)
    ["triggers/death/enable_player"]   = true,
    ["triggers/death/cooldown_player"] = 90,
    ["triggers/death/chance_player"]   = 25,
    -- Death (NPC)
    ["triggers/death/enable_npc"]      = true,
    ["triggers/death/cooldown_npc"]    = 90,
    ["triggers/death/chance_npc"]      = 25,
    -- Injury
    ["triggers/injury/enable"]         = true,
    ["triggers/injury/cooldown"]       = 20,
    ["triggers/injury/chance"]         = 25,
    ["triggers/injury/threshold"]      = 0.4,
    -- Artifact (pickup)
    ["triggers/artifact/enable_pickup"]   = true,
    ["triggers/artifact/cooldown_pickup"] = 40,
    ["triggers/artifact/chance_pickup"]   = 100,
    -- Artifact (use)
    ["triggers/artifact/enable_use"]      = true,
    ["triggers/artifact/cooldown_use"]    = 40,
    ["triggers/artifact/chance_use"]      = 100,
    -- Artifact (equip)
    ["triggers/artifact/enable_equip"]    = true,
    ["triggers/artifact/cooldown_equip"]  = 40,
    ["triggers/artifact/chance_equip"]    = 100,
    -- Anomaly (proximity)
    ["triggers/anomaly/enable_proximity"]   = true,
    ["triggers/anomaly/cooldown_proximity"] = 40,
    ["triggers/anomaly/chance_proximity"]   = 25,
    ["triggers/anomaly/max_rank_for_warning"] = 1,
    -- Anomaly (damage)
    ["triggers/anomaly/enable_damage"]     = true,
    ["triggers/anomaly/cooldown_damage"]   = 40,
    ["triggers/anomaly/chance_damage"]     = 25,
    -- Callout
    ["triggers/callout/enable"]            = true,
    ["triggers/callout/cooldown"]          = 30,
    ["triggers/callout/chance"]            = 100,
    ["triggers/callout/max_distance"]      = 30,
    ["triggers/callout/repeated_cooldown"] = 240,
    -- Taunt
    ["triggers/taunt/enable"]              = true,
    ["triggers/taunt/cooldown"]            = 120,
    ["triggers/taunt/chance"]              = 25,
    -- Emission
    ["triggers/emission/enable"]           = true,
    ["triggers/emission/chance"]           = 100,
    -- Idle
    ["triggers/idle/enable"]               = true,
    ["triggers/idle/cooldown"]             = 600,
    ["triggers/idle/chance"]               = 100,
    ["triggers/idle/question_chance"]       = 50,
    -- Idle sub-modes
    ["triggers/idle/enable_during_emission"]     = true,
    ["triggers/idle/cooldown_during_emission"]   = 30,
    ["triggers/idle/chance_during_emission"]     = 100,
    ["triggers/idle/enable_during_psy_storm"]    = true,
    ["triggers/idle/cooldown_during_psy_storm"]  = 30,
    ["triggers/idle/chance_during_psy_storm"]    = 100,
    -- Map transition
    ["triggers/map_transition/enable"]     = true,
    ["triggers/map_transition/chance"]     = 100,
    -- Sleep
    ["triggers/sleep/enable"]              = true,
    ["triggers/sleep/chance"]              = 100,
    -- Reload
    ["triggers/reload/enable"]             = true,
    ["triggers/reload/chance"]             = 10,
    -- Task
    ["triggers/task/enable"]               = true,
    ["triggers/task/cooldown"]             = 40,
    ["triggers/task/chance"]               = 10,
    -- Weapon jam
    ["triggers/weapon_jam/enable"]         = true,
    ["triggers/weapon_jam/chance"]         = 25,
}

return defaults
