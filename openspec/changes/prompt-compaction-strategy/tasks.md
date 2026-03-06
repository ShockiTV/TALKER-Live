## Tasks

### Task 1: Add MCM fields and config defaults (Lua)

Add `prompt_dialogue_pairs`, `prompt_budget_hard`, and `prompt_context_keep` to the Lua MCM and config layer.

**Files:**
- `gamedata/scripts/talker_mcm.script` — Add three `{id=..., type="input"}` entries in General Configuration section
- `bin/lua/interface/config_defaults.lua` — Add `prompt_dialogue_pairs = 3`, `prompt_budget_hard = 16`, `prompt_context_keep = 5`
- `bin/lua/interface/config.lua` — Add getter functions `prompt_dialogue_pairs()`, `prompt_budget_hard()`, and `prompt_context_keep()`

**Verify:** Run Lua tests for config module. Confirm defaults load without engine.

---

### Task 2: Mirror compaction fields in Python MCMConfig

Add the three new fields to the Python config model so they are available after `config.sync`.

**Files:**
- `talker_service/src/talker_service/models/config.py` — Add `prompt_dialogue_pairs: int = 3`, `prompt_budget_hard: int = 16`, and `prompt_context_keep: int = 5` to `MCMConfig`

**Verify:** Run Python tests for config model. Confirm fields appear in `config_mirror.dump()`.

---

### Task 3: Implement `ContextBlock.rebuild_for_candidates()`

Add the rebuild method to `ContextBlock` (introduced by `cache-friendly-prompt-layout`).

**Files:**
- The file containing `ContextBlock` (created by `cache-friendly-prompt-layout`, likely `talker_service/src/talker_service/dialogue/context_block.py`)

**Implementation:**
- Iterate `_items`, keep `StaticItem` always, keep `BackgroundItem`/`MemoryItem` if `char_id in candidate_ids` OR the item belongs to one of the last `keep_recent` non-candidate NPCs by insertion order
- Return a new `ContextBlock` instance (do not mutate original)
- Update dedup sets (`_bg_ids`, `_mem_keys`) to match retained items

**Verify:** Unit test: rebuild with 2 candidates out of 5, keep_recent=2 → 2 candidate BGs + 2 recent non-candidate BGs + statics. Test keep_recent=0 → candidates only.

---

### Task 4: Implement `compact_prompt()` function

Create the always-prune + hard-limit compactor as a pure function.

**Files:**
- `talker_service/src/talker_service/dialogue/compactor.py` (new file)

**Implementation:**
- Always trim dialogue tail to last N pairs (N = `dialogue_pairs` param)
- After trim, check estimated tokens against hard_limit
- If over hard_limit, call `context_block.rebuild_for_candidates(candidate_ids, keep_recent=context_keep)` and replace `messages[1].content`
- Return `(compacted_messages, compacted_block, cache_invalidated)`
- Use `estimate_tokens()` from `llm/token_utils.py` (only for hard limit check)

**Verify:** Unit tests: under cap, over cap, N=0, hard limit trigger, context_keep=0 (candidates only), context_keep=3 (3 recent retained), pure function guarantee.

---

### Task 5: Integrate compactor into `handle_event()`

Wire `compact_prompt()` into the conversation flow.

**Files:**
- `talker_service/src/talker_service/dialogue/conversation.py` — Call `compact_prompt()` after prompt assembly, before `complete()` call
- `talker_service/src/talker_service/dialogue/conversation.py` — Read dialogue_pairs and hard_limit from `config_mirror`

**Implementation:**
- After BGs, MEMs, and event instruction are injected
- Before `llm_client.complete(self._messages)`
- Pass `candidate_ids` from the current event context
- `dialogue_pairs = config_mirror.get("prompt_dialogue_pairs")`
- `hard_limit = config_mirror.get("prompt_budget_hard") * 1000`
- `context_keep = config_mirror.get("prompt_context_keep")`
- Replace `self._messages` and `self._context_block` with returned values

**Verify:** Integration test: simulate 50 events, confirm prompt size stays bounded. E2E test: dialogue generates correctly after compaction.

---

### Task 6: Remove old pruning.py

Delete the superseded pruning module and update imports.

**Files:**
- `talker_service/src/talker_service/llm/pruning.py` — DELETE
- Any file importing `prune_conversation` — Remove/replace import

**Verify:** `grep -r "prune_conversation\|from.*pruning" talker_service/src/` returns no hits. All tests pass.

---

### Task 7: Update tests

Add new tests and update existing ones.

**Files:**
- `talker_service/tests/unit/test_compactor.py` (new) — Unit tests for `compact_prompt()`
- `talker_service/tests/unit/test_context_block.py` (update) — Tests for `rebuild_for_candidates()` including `keep_recent` param
- `talker_service/tests/unit/test_pruning.py` or similar — DELETE or replace with compactor tests
- `talker_service/tests/e2e/` — Verify existing e2e scenarios still pass with new compaction

**Verify:** Full test suite passes. No references to old pruning module.
