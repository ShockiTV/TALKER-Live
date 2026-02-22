## ~~ADDED Requirements~~ (Superseded)

> **All requirements in this spec were superseded during implementation.**
> NPCs use their engine-assigned voice theme (`npc:sound_prefix()`) directly.
> `voice_id` is resolved on-demand at `tts.speak` time in
> `talker_zmq_command_handlers.script` via `engine.get_sound_prefix(obj)`.
> No Lua-side voice cache, faction pools, persistence, or character-model
> integration is needed.
>
> The following modules were implemented then intentionally deleted:
> - `bin/lua/domain/data/voice_data.lua`
> - `bin/lua/domain/repo/voices.lua`
> - `tests/domain/test_voices.lua`
> - `voice_id` field in `character.lua`, `serializer.lua`, and `talker_game_persistence.script`
