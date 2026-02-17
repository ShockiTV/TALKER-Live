## 1. Lua Changes - Send Technical IDs

- [x] 1.1 Update `bin/lua/infra/game_adapter.lua` to send raw faction ID instead of calling `get_faction_name()`
- [x] 1.2 Update `bin/lua/infra/game_adapter.lua` to send raw reputation integer instead of calling `get_reputation_tier()`

## 2. Python Data Models - Type Changes

- [x] 2.1 Update `talker_service/src/talker_service/prompts/models.py` Character.reputation type from `str` to `int`
- [x] 2.2 Update `talker_service/src/talker_service/state/models.py` Character.reputation type from `str` to `int`

## 3. Python Faction Resolution

- [x] 3.1 Re-key `FACTION_DESCRIPTIONS` dict in `prompts/factions.py` by technical faction IDs (dolg, killer, csky, etc.)
- [x] 3.2 Add `FACTION_NAMES` dict mapping technical ID to display name in `prompts/factions.py`
- [x] 3.3 Add `resolve_faction_name(faction_id)` function in `prompts/factions.py`
- [x] 3.4 Update `get_faction_description()` to use technical ID keys

## 4. Python Reputation Changes

- [x] 4.1 Update Character.reputation type to int in prompts/models.py
- [x] 4.2 Update Character.reputation type to int in state/models.py
- [x] 4.3 Update REPUTATION_RULES in builder.py to describe numeric scale
- [x] 4.4 Update prompt builder to display numeric reputation value

## 5. Python Lookup Exports

- [x] 5.1 Export `resolve_faction_name` from `prompts/lookup.py`

## 6. Python Prompt Builder Integration

- [x] 6.1 Update dialogue prompt builder to resolve faction ID to display name for prompt text
- [x] 6.2 Update helpers.py to resolve visual_faction (disguise) to display name
- [x] 6.3 Update speaker selection prompt if it displays faction

## 7. Test Updates

- [x] 7.1 Update Python test fixtures to use technical faction IDs instead of display names
- [x] 7.2 Update Python test fixtures to use integer reputation instead of string tiers
- [x] 7.3 Update test fixtures for visual_faction to use technical IDs
- [x] 7.4 Add unit tests for `resolve_faction_name()` function
- [x] 7.5 Run full Python test suite and fix any remaining failures
