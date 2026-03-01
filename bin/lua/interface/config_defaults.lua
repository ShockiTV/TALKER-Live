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
    base_dialogue_chance    = 0.25,
    witness_distance        = 25,
    npc_speak_distance      = 30,
    time_gap                = 4,

    -- WebSocket / service
    ws_host                 = "127.0.0.1",
    mic_ws_port             = 5558,
    service_url             = "wss://talker-live.duckdns.org/ws",
    ws_token                = "",
    llm_timeout             = 60,
    state_query_timeout     = 30,

    -- TTS
    tts_volume_boost        = 8.0,

    -- Debug
    debug_logging           = 2,
    max_log_entries_per_level = 0,

    -- Save management
    reset_backstory         = false,
    reset_personality       = false,

    -- Trigger settings
    recent_speech_threshold         = 120,
    idle_question_chance            = 0.5,
    idle_conversation_cooldown      = 600,
    enable_trigger_idle             = true,
    enable_trigger_callout          = true,
    max_callout_distance            = 30,
    callout_cooldown                = 30,
    repeated_callout_cooldown       = 240,
    enable_trigger_taunt            = true,
    taunt_cooldown                  = 120,
    enable_trigger_death_player     = 0,
    death_cooldown_player           = 90,
    enable_trigger_death_npc        = 0,
    death_cooldown_npc              = 90,
    enable_trigger_reload           = 0,
    reload_notice_chance            = 0.1,
    enable_trigger_injury           = 0,
    injury_threshold                = 0.4,
    injury_cooldown                 = 20,
    enable_trigger_emission         = 0,
    enable_trigger_map_transition   = 0,
    enable_trigger_task             = 0,
    task_cooldown                   = 40,
    task_notice_chance              = 0.1,
    enable_trigger_sleep            = 0,
    enable_trigger_weapon_jam       = 0,
    enable_trigger_proximity_anomalies = 0,
    max_rank_for_warning            = 1,
    anomaly_proximity_comment_cd    = 40,
    enable_trigger_damage_anomalies = 0,
    anomaly_damage_comment_cd       = 40,
    enable_trigger_artifact_pickup  = 0,
    artifact_pickup_comment_cd      = 40,
    enable_trigger_artifact_use     = 0,
    artifact_use_comment_cd         = 40,
    enable_trigger_artifact_equip   = 0,
    artifact_equip_comment_cd       = 40,
}

return defaults
