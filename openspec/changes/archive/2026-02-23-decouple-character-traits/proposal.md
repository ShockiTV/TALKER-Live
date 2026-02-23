## Why

The `Character` entity in Lua has become a "god object" that mixes raw engine state with domain-level narrative concepts (backstory and personality). This creates unnecessary coupling, bloats the ZMQ event payloads (since every witness in every event carries full narrative strings), and creates a risk of stale data if a character's personality changes. By decoupling these traits and fetching them on-demand via `BatchQuery`, we can simplify the Lua architecture, reduce payload sizes, and centralize narrative logic in Python.

## What Changes

- **BREAKING**: Remove `backstory` and `personality` fields from the `Character` entity in both Lua and Python.
- **BREAKING**: Remove `Character.describe` and `Character.describe_short` from Lua (formatting is now exclusively Python's job).
- Update Lua's `game_adapter.lua` to stop fetching narrative traits when constructing a `Character`.
- Update Lua's `talker_zmq_query_handlers.script` so that `store.personalities` and `store.backstories` resolvers automatically generate and save missing traits when queried.
- Update Python's `DialogueGenerator` to fetch `store.personalities` for all witnesses before picking a speaker.
- Update Python's `DialogueGenerator` to fetch `store.backstories` and `store.personalities` for the chosen speaker before generating dialogue.
- Update Python's prompt builders (`create_pick_speaker_prompt` and `create_dialogue_request_prompt`) to accept narrative traits as separate arguments rather than reading them from the `Character` object.

## Capabilities

### New Capabilities
- `character-traits-query`: Defines how Python fetches decoupled character traits (personalities and backstories) on demand via BatchQuery.

### Modified Capabilities
- `lua-state-query-handler`: Update the `store.personalities` and `store.backstories` resolvers to support lazy-generation of missing traits.
- `batch-query-protocol`: Update the expected return types and behavior for `store.personalities` and `store.backstories` to guarantee trait assignment.

## Impact

- **Lua**: `domain/model/character.lua`, `infra/game_adapter.lua`, `gamedata/scripts/talker_zmq_query_handlers.script`, `domain/repo/personalities.lua`, `domain/repo/backstories.lua`.
- **Python**: `state/models.py`, `dialogue/generator.py`, `prompts/speaker.py`, `prompts/dialogue.py`.
- **ZMQ Payload**: `game.event` payloads will be significantly smaller as `witnesses` will no longer contain `backstory` and `personality` strings.
- **Tests**: All tests relying on the old `Character` structure (both Lua and Python) will need to be updated.