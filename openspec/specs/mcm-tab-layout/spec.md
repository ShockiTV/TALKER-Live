# mcm-tab-layout

## Purpose

Reorganize the TALKER MCM (Mod Configuration Menu) from a flat single-tab layout into 6 logical tabs, with a new Connection tab for service type, remote hub, branch selection, and authentication fields.

## Requirements

### Requirement: Six-tab MCM structure

The MCM SHALL be organized into 6 tabs: General, AI Model, Voice, Connection, Triggers, and Debug. Each tab SHALL use the MCM framework's `{id}_subtab` pattern for tab registration.

#### Scenario: All six tabs visible in MCM

- **WHEN** the player opens the TALKER MCM settings
- **THEN** 6 tabs SHALL be visible: General, AI Model, Voice, Connection, Triggers, Debug
- **AND** each tab SHALL contain only the settings listed for that tab

### Requirement: General tab settings

The General tab SHALL contain: `language`, `action_descriptions`, `female_gender`, `witness_distance`, `npc_speak_distance`.

#### Scenario: General tab contains expected settings

- **WHEN** the player navigates to the General tab
- **THEN** the following settings SHALL be present: language selector, action descriptions toggle, female gender toggle, witness distance slider, NPC speak distance slider

### Requirement: AI Model tab settings

The AI Model tab SHALL contain: `ai_model_method`, `custom_ai_model`, `custom_ai_model_fast`, `reasoning_level`, `ai_base_url`, `openrouter_api_key`, `openai_api_key`, `ollama_base_url`.

#### Scenario: AI Model tab contains provider settings

- **WHEN** the player navigates to the AI Model tab
- **THEN** the following settings SHALL be present: AI model method selector, model name inputs, reasoning toggle, base URL input, API key inputs, Ollama base URL input

### Requirement: Voice tab settings

The Voice tab SHALL contain: `input_option`, `speak_key`, `voice_provider`, `enable_tts`, `tts_voice_method`.

#### Scenario: Voice tab contains input and TTS settings

- **WHEN** the player navigates to the Voice tab
- **THEN** the following settings SHALL be present: input method selector, speak key binding, STT method selector, TTS enable toggle, TTS voice method selector

### Requirement: Connection tab settings

The Connection tab SHALL contain settings organized in sections with separator headers:

**Service Type section:**
- `service_type` — radio with options: Local (0), Remote (1). Default: Local.

**Remote section (header: "-- Remote --"):**
- `service_hub_url` — text input for the hub domain (e.g., `https://talker-live.duckdns.org`). Default: empty.
- `branch` — radio with options: main (0), dev (1), custom (2). Default: main.
- `custom_branch` — text input for custom branch name. Default: empty.

**Local section (header: "-- Local --"):**
- `service_url` — text input. Default: empty (uses `ws://127.0.0.1:<port>/ws`).

**Auth section (header: "-- Auth --"):**
- `auth_username` — text input. Default: empty.
- `auth_password` — text input. Default: empty.
- `auth_client_id` — text input. Default: `talker-client`.
- `auth_client_secret` — text input. Default: empty.

**Advanced section (header: "-- Advanced --"):**
- `llm_timeout` — numeric input (seconds). Default: 60.
- `state_query_timeout` — numeric input (seconds). Default: 10.

#### Scenario: Connection tab displays all sections

- **WHEN** the player navigates to the Connection tab
- **THEN** Service Type, Remote, Local, Auth, and Advanced sections SHALL all be visible
- **AND** all fields SHALL be present regardless of the service_type selection

#### Scenario: Service type defaults to Local

- **WHEN** the player has not changed any Connection settings
- **THEN** `service_type` SHALL be 0 (Local)
- **AND** `branch` SHALL be 0 (main)
- **AND** `auth_client_id` SHALL be `talker-client`

#### Scenario: Remote service type with hub URL

- **WHEN** the player sets `service_type` to Remote and enters `https://talker-live.duckdns.org` in `service_hub_url`
- **THEN** `config.get_all_config()` SHALL include `service_type: 1` and `service_hub_url: "https://talker-live.duckdns.org"`

#### Scenario: Custom branch text field

- **WHEN** the player sets `branch` to custom (2) and enters `feature-xyz` in `custom_branch`
- **THEN** `config.get_all_config()` SHALL include `branch: 2` and `custom_branch: "feature-xyz"`

### Requirement: Triggers tab with General sub-section

The Triggers tab SHALL contain a new "General" sub-section at the top with settings that apply across all triggers: `time_gap`, `recent_speech_threshold`, `anti_spam_cd`, `speaker_pick_max_events`. The existing per-trigger toggles and parameter sliders SHALL remain in their current sub-sections below.

#### Scenario: Trigger general settings in Triggers tab

- **WHEN** the player navigates to the Triggers tab
- **THEN** a "General" sub-section SHALL appear at the top with: time_gap, recent_speech_threshold, anti_spam_cd, speaker_pick_max_events
- **AND** existing per-trigger sections (death, injury, artifact, etc.) SHALL follow below

### Requirement: Debug tab settings

The Debug tab SHALL contain: `debug_logging` and any reset/diagnostic buttons.

#### Scenario: Debug tab contains logging settings

- **WHEN** the player navigates to the Debug tab
- **THEN** `debug_logging` level selector SHALL be present
- **AND** any reset controls SHALL be grouped in this tab

### Requirement: MCM keys unchanged for backward compatibility

All existing MCM setting keys SHALL remain identical. Moving a setting from one tab to another SHALL NOT change its key string. New settings SHALL use the keys specified in the Connection tab requirement. Player saved configurations SHALL continue to work after the tab reorganization.

#### Scenario: Existing saved configs preserved

- **WHEN** a player upgrades from the old single-tab MCM to the new 6-tab MCM
- **THEN** all previously saved settings SHALL retain their values
- **AND** no manual reconfiguration SHALL be required

### Requirement: MCM localization strings

New tab names and field labels SHALL be added to `gamedata/configs/text/eng/talker_mcm.xml`. Tab names: "General", "AI Model", "Voice", "Connection", "Triggers", "Debug". Section headers and field descriptions for all new Connection fields SHALL be included.

#### Scenario: Connection tab fields have descriptions

- **WHEN** the player hovers over `service_hub_url` in the Connection tab
- **THEN** a tooltip/description SHALL explain the field (e.g., "URL of the shared TALKER service hub. Leave empty for local mode.")
