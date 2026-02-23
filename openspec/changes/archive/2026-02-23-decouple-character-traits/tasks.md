## Phase 1: Lua Character DTO Refactor

- [x] **Task 1.1: Update Lua Character Entity**
  - File: `bin/lua/domain/model/character.lua`
  - Action: Remove `backstory` and `personality` fields from the `Character` table structure.
  - Action: Remove `Character.describe` and `Character.describe_short` functions.
- [x] **Task 1.2: Update Lua Game Adapter**
  - File: `bin/lua/infra/game_adapter.lua`
  - Action: Modify `game_adapter.create_character` to stop fetching and assigning `backstory` and `personality`.
- [x] **Task 1.3: Fix Lua Tests (Character)**
  - Files: `tests/domain/model/test_character.lua`, `tests/infra/test_game_adapter.lua`, and any other tests relying on `Character.describe` or the removed fields.
  - Action: Update test assertions and mocks to reflect the new Lean DTO structure.

## Phase 2: Lua Lazy Generation

- [x] **Task 2.1: Update ZMQ Query Handlers**
  - File: `gamedata/scripts/talker_zmq_query_handlers.script`
  - Action: Modify the `store.personalities` resolver. If `repo.get(id)` returns nil, call `repo.generate_for_character(char)`, save it, and return the new ID.
  - Action: Modify the `store.backstories` resolver. If `repo.get(id)` returns nil, call `repo.generate_for_character(char)`, save it, and return the new ID.
- [x] **Task 2.2: Fix Lua Tests (Query Handlers)**
  - Files: `tests/interface/test_zmq_query_handlers.lua` (or equivalent).
  - Action: Add tests to verify that querying a missing trait triggers generation and returns a valid ID.

## Phase 3: Python Character DTO Refactor

- [x] **Task 3.1: Update Python Character Model**
  - File: `talker_service/src/talker_service/state/models.py`
  - Action: Remove `backstory` and `personality` fields from the `Character` dataclass/Pydantic model.
- [x] **Task 3.2: Fix Python Tests (Models)**
  - Files: `talker_service/tests/state/test_models.py` (or equivalent).
  - Action: Update test fixtures and assertions to reflect the removed fields.
- [x] **Task 3.3: Update ZMQ API Contract**
  - File: `docs/zmq-api.yaml`
  - Action: Remove `backstory` and `personality` from the `Character` schema definition to reflect the new Lean DTO structure.

## Phase 4: Python Two-Phase Fetch & Prompt Updates

- [x] **Task 4.1: Update Prompt Builders**
  - Files: `talker_service/src/talker_service/prompts/speaker.py`, `talker_service/src/talker_service/prompts/dialogue.py`
  - Action: Modify `create_pick_speaker_prompt` to accept a `Dict[str, str]` of personalities instead of reading from `Character` objects.
  - Action: Modify `create_dialogue_request_prompt` to accept `speaker_personality` and `speaker_backstory` as explicit string arguments.
- [x] **Task 4.2: Implement Two-Phase Fetch in DialogueGenerator**
  - File: `talker_service/src/talker_service/dialogue/generator.py`
  - Action: In `_pick_speaker`, execute a `BatchQuery` to fetch `store.personalities` for all valid witnesses. Pass the result to the updated prompt builder.
  - Action: In `_generate_dialogue_for_speaker`, execute a `BatchQuery` to fetch `store.backstories` (and memory) for the chosen speaker. Pass the results to the updated prompt builder.
- [x] **Task 4.3: Fix Python Tests (Generator & Prompts)**
  - Files: `talker_service/tests/dialogue/test_generator.py`, `talker_service/tests/prompts/test_speaker.py`, `talker_service/tests/prompts/test_dialogue.py`, and E2E tests.
  - Action: Update mocks for `StateQueryClient` to handle the new two-phase `BatchQuery` calls. Update prompt tests to pass the new explicit arguments.
