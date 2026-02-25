# voice-profile-store

## Purpose

Originally defined a Lua-side voice profile store for NPC voice assignment. All requirements were superseded — NPCs use their engine-assigned voice theme directly via `npc:sound_prefix()`.

## Requirements

### Requirement: Voice profile store is not implemented (superseded)

The system SHALL NOT maintain a Lua-side voice cache, faction voice pools, or persistence for voice profiles. Voice IDs SHALL be resolved on-demand via `engine.get_sound_prefix(obj)` at TTS generation time.

#### Scenario: No voice store modules exist
- **WHEN** the codebase is inspected
- **THEN** `bin/lua/domain/data/voice_data.lua`, `bin/lua/domain/repo/voices.lua`, and `tests/domain/test_voices.lua` do not exist
- **AND** the `Character` entity does not contain a `voice_id` field
