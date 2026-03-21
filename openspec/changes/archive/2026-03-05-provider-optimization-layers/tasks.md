# Implementation Tasks: Provider Optimization Layers

## Task Organization

Tasks are grouped by capability and ordered by dependencies. Each task includes acceptance criteria and verification steps.

---

## Phase 1: OpenAI Persistent Conversation

### Task 1.1: Add llm_client field to SessionContext
**File**: `talker_service/src/talker_service/transport/session.py`
- [x] Add `llm_client: LLMClient | None = None` field to `SessionContext` dataclass
- [x] Add docstring: "Per-session LLM client with isolated conversation state"

**Acceptance**:
- Field present in SessionContext
- Defaults to `None`

### Task 1.2: Add conversation state to OpenAIClient
**File**: `talker_service/src/talker_service/llm/openai_client.py`
- [x] Add `_conversation: list[Message]` field to `__init__`
- [x] Update `complete_with_tools()` to append messages to `_conversation` instead of creating fresh list
- [x] Ensure `complete()` still works for non-tool use cases (or deprecate if unused)

**Acceptance**:
- `_conversation` persists across multiple `complete_with_tools()` calls
- Unit test: call `complete_with_tools()` twice, verify `_conversation` contains both exchanges

### Task 1.3: Add conversation reset method
**File**: `talker_service/src/talker_service/llm/openai_client.py`
- [x] Add `reset_conversation()` method to clear `_conversation` list
- [x] Add `get_conversation()` method for debugging/testing

**Acceptance**:
- `reset_conversation()` clears the list
- Unit test: populate conversation, reset, verify empty

### Task 1.4: Add LLM client factory method
**File**: `talker_service/src/talker_service/__main__.py`
- [x] Add `_create_session_llm_client(session_id: str) -> LLMClient` function
- [x] Factory should respect current MCM config (model_method, model_name, etc.)
- [x] Use `get_llm_client()` from `llm/factory.py` with current settings

**Acceptance**:
- Factory returns OpenAI client configured per current settings
- Unit test: verify factory respects config values

### Task 1.5: Update ConversationManager to use session-scoped clients
**File**: `talker_service/src/talker_service/dialogue/conversation.py`
- [x] Remove `self.llm_client` field from `__init__`
- [x] Add `self.session_registry` field (passed in constructor)
- [x] Add `self.llm_client_factory` field (callable that creates clients)
- [x] Update `handle_event()` signature: add `session_id: str` parameter
- [x] In `handle_event()`: retrieve session, check if `session.llm_client` exists, create if `None`
- [x] Use `session.llm_client` for all LLM calls within that event

**Acceptance**:
- ConversationManager retrieves client from session context
- If client is None, factory creates new instance
- Messages accumulate in session-scoped client across events

### Task 1.6: Wire session_id through event handlers
**File**: `talker_service/src/talker_service/handlers/events.py`
- [x] Update `handle_game_event()` to pass `session_id` to `conversation_manager.handle_event()`
- [x] Session ID already available in handler context

**Acceptance**:
- Session ID flows from WebSocket handler → event handler → ConversationManager

### Task 1.7: Update __main__.py initialization
**File**: `talker_service/src/talker_service/__main__.py`
- [x] Remove singleton `llm_client` from ConversationManager constructor
- [x] Pass `session_registry` to ConversationManager
- [x] Pass `llm_client_factory` (reference to `_create_session_llm_client`)

**Acceptance**:
- ConversationManager no longer receives singleton client
- Factory and registry passed correctly

---

## Phase 2: Context-Aware Message Pruning

### Task 2.1: Add token estimation utility
**File**: `talker_service/src/talker_service/llm/token_utils.py` (NEW)
- [x] Create `estimate_tokens(messages: list[Message]) -> int` function
- [x] Use 4 chars/token heuristic initially (or import `tiktoken` for accuracy)
- [x] Add `estimate_message_tokens(message: Message) -> int` helper

**Acceptance**:
- Unit test: sample messages return reasonable token counts
- Verify against OpenAI's official token counter (manual spot-check)

### Task 2.2: Implement pruning algorithm
**File**: `talker_service/src/talker_service/llm/pruning.py` (NEW)
- [x] Create `prune_conversation(messages: list[Message], max_tokens: int, target_tokens: int) -> list[Message]`
- [x] Implement priority-based removal:
  1. Preserve system prompts (role="system")
  2. Preserve last 5 user/assistant pairs (last 10 messages)
  3. Preserve last 5 tool call/result pairs
  4. Remove older dialogue messages (user/assistant)
  5. Remove older tool messages
- [x] Return pruned list maintaining chronological order

**Acceptance**:
- Unit test: 100-message conversation → prunes to target while preserving recent/system
- Verify system prompts never removed
- Verify last 5 dialogue pairs always kept

### Task 2.3: Integrate pruning into OpenAIClient
**File**: `talker_service/src/talker_service/llm/openai_client.py`
- [x] Import `estimate_tokens()` and `prune_conversation()`
- [x] Before API call in `complete_with_tools()`, check token count
- [x] If > 96k tokens (75% of 128k), prune to 64k tokens (50%)
- [x] Log pruning events: "Pruned conversation: {before} → {after} tokens"

**Acceptance**:
- Integration test: populate 100k token conversation, trigger pruning on next call
- Verify conversation size reduced to ~50%
- Verify API call succeeds

### Task 2.4: Add pruning metrics
**File**: `talker_service/src/talker_service/llm/openai_client.py`
- [x] Track: `pruning_events_count`, `tokens_removed_total`, `avg_conversation_tokens`
- [x] Log metrics periodically or expose via debug endpoint

**Acceptance**:
- Metrics update when pruning occurs
- `/health` or `/debug/config` shows conversation stats

---

## Phase 3: Multi-NPC Tool Batching

### Task 3.1: Update background tool schema
**File**: `talker_service/src/talker_service/dialogue/conversation.py`
- [x] Change `BACKGROUND_TOOL` schema: `character_ids: list[str]` (instead of `character_id: str`)
- [x] Update description: "Fetch backgrounds for multiple NPCs at once"
- [x] Add validation: max 10 NPCs

**Acceptance**:
- Schema accepts `character_ids` array
- Unit test: verify schema validates correctly

### Task 3.2: Update background handler for batching
**File**: `talker_service/src/talker_service/dialogue/conversation.py` (`_handle_background()`)
- [x] Accept both `character_id: str` and `character_ids: list[str]` (normalize to list)
- [x] Build BatchQuery with `batch.add(char_id, "background", {"character_id": char_id})` for each
- [x] Execute batch: `result = await self.state_client.execute_batch(batch)`
- [x] Return `dict[str, dict]` where keys are character IDs

**Acceptance**:
- Handler accepts singular string (backward compat)
- Handler accepts array of character IDs
- Returns dict with all requested backgrounds
- Integration test: request 3 NPCs, verify 3 results

### Task 3.3: Update get_character_info tool schema
**File**: `talker_service/src/talker_service/dialogue/conversation.py`
- [x] Change `GET_CHARACTER_INFO_TOOL` schema: `character_ids: list[str]`
- [x] Update description: "Fetch character info for multiple NPCs"
- [x] Add validation: max 10 NPCs

**Acceptance**:
- Schema accepts `character_ids` array

### Task 3.4: Update get_character_info handler for batching
**File**: `talker_service/src/talker_service/dialogue/conversation.py` (`_handle_get_character_info()`)
- [x] Accept both `character_id: str` and `character_ids: list[str]`
- [x] Build BatchQuery for character info
- [x] Execute batch, return `dict[str, dict]`

**Acceptance**:
- Handler accepts singular string or array
- Returns dict with all requested character info
- Integration test: request 5 NPCs, verify 5 results

### Task 3.5: Add batch size validation
**File**: `talker_service/src/talker_service/dialogue/conversation.py`
- [x] In both handlers, validate `len(character_ids) <= 10`
- [x] Return error message if exceeded: "Batch size limit: 10 NPCs max"

**Acceptance**:
- Attempt 11 NPCs → returns error message
- Unit test: verify validation logic

---

## Phase 4: Speaker-Restricted Memory Queries

### Task 4.1: Update get_memories tool schema
**File**: `talker_service/src/talker_service/dialogue/conversation.py`
- [x] Keep `GET_MEMORIES_TOOL` with singular `character_id: str` (NOT array)
- [x] Make `tiers` parameter optional: remove from `required` list
- [x] Update description: "Retrieve memories for THE CHOSEN SPEAKER ONLY. Do NOT use for candidate evaluation—use backgrounds instead."

**Acceptance**:
- Schema requires `character_id` (singular)
- Schema does not require `tiers`
- Unit test: verify schema validates correctly

### Task 4.2: Update get_memories handler for optional tiers
**File**: `talker_service/src/talker_service/dialogue/conversation.py` (`_handle_get_memories()`)
- [x] Default `tiers` to all four tiers if omitted: `["events", "summaries", "digests", "cores"]`
- [x] Keep existing logic for executing memory query

**Acceptance**:
- Call without `tiers` → returns all 4 tiers
- Call with explicit `tiers=["events"]` → returns only events
- Integration test: verify both cases

### Task 4.3: Update system prompt with workflow instructions
**File**: `talker_service/src/talker_service/dialogue/conversation.py` (`_build_system_prompt()`)
- [x] Add "Tool Usage Rules" section to system prompt (see spec example)
- [x] Emphasize workflow: backgrounds for all candidates → choose speaker → memories for speaker only
- [x] Explain cost rationale: "Memories are expensive; use backgrounds for speaker selection"

**Acceptance**:
- System prompt includes workflow instructions
- Unit test: verify prompt contains expected text

### Task 4.4: Add memory query logging
**File**: `talker_service/src/talker_service/dialogue/conversation.py` (`_handle_get_memories()`)
- [x] Log at INFO level: "Fetching memories for speaker {char_id} (tiers: {tiers})"

**Acceptance**:
- Log entry appears when memories queried
- Log shows which tiers were requested

---

## Phase 5: Testing & Validation

### Task 5.1: Unit tests for OpenAIClient conversation
**File**: `talker_service/tests/unit/llm/test_openai_client.py` (NEW or append)
- [x] Test: `_conversation` persists across calls
- [x] Test: `reset_conversation()` clears state
- [x] Test: `get_conversation()` returns current state

**Acceptance**:
- All tests pass
- Coverage for new methods >90%

### Task 5.2: Unit tests for pruning logic
**File**: `talker_service/tests/unit/llm/test_pruning.py` (NEW)
- [x] Test: system prompts never removed
- [x] Test: last 5 dialogue pairs preserved
- [x] Test: older messages removed first
- [x] Test: pruning stops at target token count

**Acceptance**:
- All tests pass
- Edge cases covered (empty conversation, all-system, etc.)

### Task 5.3: Unit tests for batch tool handlers
**File**: `talker_service/tests/unit/dialogue/test_conversation.py`
- [x] Test: background handler accepts string or array
- [x] Test: get_character_info handler accepts string or array
- [x] Test: batch size validation rejects >10 NPCs
- [x] Test: batch results returned as dict

**Acceptance**:
- All tests pass
- Backward compatibility verified (singular strings still work)

### Task 5.4: Integration test for speaker selection workflow
**File**: `talker_service/tests/integration/test_speaker_workflow.py` (NEW)
- [x] Scenario: 5 candidates → LLM calls background(character_ids=[...]) → chooses speaker → calls get_memories(character_id=...) → generates dialogue
- [x] Verify: only 2-3 tool calls total (not 6+)
- [x] Verify: memories fetched only for speaker

**Acceptance**:
- End-to-end workflow completes successfully
- Tool usage count validates efficiency gains

### Task 5.5: E2E test for long conversation
**File**: `talker_service/tests/e2e/test_long_conversation.py` (NEW)
- [x] Simulate 20+ events with same OpenAIClient instance
- [x] Verify: conversation grows, pruning triggers, API calls succeed
- [x] Verify: dialogue quality maintained after pruning

**Acceptance**:
- No crashes or API errors after 20+ events
- Pruning events logged correctly

---

## Phase 6: Documentation & Rollout

### Task 6.1: Update ws-api.yaml (if needed)
**File**: `docs/ws-api.yaml`
- [x] Document batch query format for tools (if not already covered)
- [x] Note optional tiers parameter for get_memories

**Acceptance**:
- API docs reflect tool schema changes

### Task 6.2: Update Python_Service_Setup.md
**File**: `docs/Python_Service_Setup.md`
- [x] Add section on conversation persistence
- [x] Add section on context window management
- [x] Add troubleshooting: what if conversation grows too large?

**Acceptance**:
- Documentation clear for users
- Setup instructions include any new config values

### Task 6.3: Add feature flag (optional)
**File**: `talker_service/src/talker_service/config.py`
- [x] Add `enable_conversation_persistence: bool = True` (if gradual rollout desired)
- [x] Add `enable_context_pruning: bool = True`

**Acceptance**:
- Features can be toggled via `.env`

### Task 6.4: Monitor initial rollout
- [x] Deploy to dev environment
- [x] Run 10+ test sessions, monitor logs
- [x] Check for: pruning frequency, tool usage patterns, API errors
- [x] Verify token costs align with expectations

**Acceptance**:
- No critical errors in dev
- Token usage reduced vs. baseline
- Dialogue quality maintained per user feedback

---

## Summary

**Total Tasks**: 31 (10 for phase 1, 4 for phase 2, 5 for phase 3, 4 for phase 4, 4 for testing, 4 for docs/rollout)

**Estimated Effort**:
- Phase 1: 1.5 days (session context integration + factory pattern)
- Phase 2: 1.5 days (pruning logic + testing)
- Phase 3: 1 day (batch handlers + validation)
- Phase 4: 0.5 day (optional param + system prompt)
- Phase 5: 1 day (comprehensive tests including session isolation)
- Phase 6: 0.5 day (docs + rollout)

**Total**: ~6 days

**Dependencies**:
- Phase 1 → Phase 2 (pruning needs conversation state)
- Phase 3 → Phase 4 (speaker restriction relies on batch backgrounds)
- Phases 1-4 → Phase 5 (tests validate all features)
- Phase 5 → Phase 6 (rollout after tests pass)

**Success Criteria**:
- ✅ All 31 tasks completed
- ✅ All tests passing (unit, integration, e2e)
- ✅ Session isolation verified (multiple concurrent games maintain separate conversations)
- ✅ No regressions in existing dialogue quality
- ✅ Tool usage count reduced for multi-candidate events
- ✅ Conversation persists across events within same session
- ✅ No memory leaks or cross-session contamination
- ✅ Token costs remain within OpenAI budget
