## Context

The STALKER Anomaly game engine maintains a live faction×faction relation matrix (`relation_registry.community_relation(a, b)`) and per-faction player goodwill (`actor:community_goodwill(faction)`). Both are **dynamic** — they shift with warfare territory changes, quest completions, and NPC kills. Currently, the Python service uses a hardcoded `FACTION_RELATIONS` dict in `prompts/factions.py` with static -1/0/1 values, which cannot reflect in-game changes. The `query.world` handler returns scene data (location, time, weather, campfire, brain scorcher/miracle machine status) but has no faction data at all.

9 primary factions participate in the matrix: stalker, dolg, freedom, csky, ecolog, killer, army, bandit, monolith (with renegade/greh/isg swapped depending on player faction). That's 36 unique directional pairs + 9 goodwill values.

## Goals / Non-Goals

**Goals:**
- Expose live faction standings and player goodwill in `query.world` so Python prompts reflect actual game state
- Format faction data into human-readable prompt text with threshold-based labels
- Extend `SceneContext` to carry faction data through the existing prompt builder pipeline
- Add companion faction tension note so companions express faction attitudes in dialogue
- Keep changes backward-compatible (Python defaults missing fields to empty)

**Non-Goals:**
- Disguise system changes — the existing disguise flow (visual_faction on Character, prompt injection in helpers.py) is preserved as-is; no redesign here
- NPC-to-NPC personal goodwill (individual `relation_registry.community_goodwill` per NPC pair) — too granular, revisit later
- Individual NPC→player personal relations — only faction-level goodwill
- MCM settings for faction display (e.g., toggling faction text) — can be added later without architectural changes
- Removing the static `FACTION_RELATIONS` dict — it stays as test/offline fallback

## Decisions

### Decision 1: Faction matrix as flat dict, not nested

**Choice**: `{"dolg_freedom": -1500, "stalker_bandit": -800, ...}` (36 keys, underscore-delimited pair)

**Alternatives considered**:
- Nested dict `{"dolg": {"freedom": -1500, ...}}` — more natural in Python but doubles serialization complexity in Lua and adds JSON nesting
- Array of tuples `[["dolg", "freedom", -1500], ...]` — harder to look up by pair

**Rationale**: Flat dict is cheapest to build in Lua (`pairs()` over a faction list), serializes trivially to JSON, and Python can split keys on `_` if needed. The underscore delimiter is unambiguous since no faction ID contains underscores.

### Decision 2: Raw numeric values from engine, labels in Python

**Choice**: Lua sends raw integers (e.g., -1500, 0, 1200). Python applies threshold labels.

**Alternatives considered**:
- Lua applies labels before sending — duplicates threshold logic across codebases
- Send both raw + label — bloats payload

**Rationale**: Python already owns prompt formatting. Engine thresholds are stable constants (`game_relations.script`): ≥1000 = Allied, ≤-1000 = Hostile, between = Neutral. Goodwill tiers use PDA-style thresholds (≥2000 Excellent, ≥1500 Brilliant, etc.). Defining these in Python keeps the labeling co-located with prompt text generation.

### Decision 3: Inline in query.world, not separate query

**Choice**: Add `faction_standings` and `player_goodwill` as optional fields in the existing `query.world` response.

**Alternatives considered**:
- New `query.factions` resource — requires another sub-query in every batch, more WS overhead
- Embed in event payload — wrong layer (events are about what happened, not about world state)

**Rationale**: Faction data is world state. `query.world` already carries scene context (location, weather, time). Adding two more keys keeps the batch query count unchanged. The data is small (~600 bytes JSON) and changes infrequently within a session.

### Decision 4: Filter to relevant factions only

**Choice**: The Lua builder iterates all 9 factions but Python's formatter only includes factions that appear in the current event's context (speaker faction, witness factions, mentioned factions). Full matrix is available in `SceneContext` for ad-hoc lookups.

**Alternatives considered**:
- Send only relevant pairs from Lua — requires Lua to know which factions matter for the current event, coupling query handler to event logic
- Always format all 36 pairs — wastes ~150 tokens on irrelevant faction pairs

**Rationale**: Lua sends the full matrix cheaply (one pass). Python filters during prompt formatting, where it knows which factions are contextually relevant. The full matrix remains accessible for the LLM tool calling path (future) where the LLM may want to query arbitrary pairs.

### Decision 5: SceneContext extension with optional fields

**Choice**: Add `faction_standings: dict[str, int] | None = None` and `player_goodwill: dict[str, int] | None = None` to `SceneContext`.

**Alternatives considered**:
- Separate `FactionContext` dataclass — adds another model for two dict fields
- Inline in WorldContext — WorldContext is the older model being phased out for SceneContext

**Rationale**: Minimal change. `None` default means existing serialized data without faction fields still parses correctly. SceneContext is the active model used in prompt building.

### Decision 6: Companion faction tension as system prompt note

**Choice**: Add a static note in the system prompt: "Faction hostilities apply to your attitude and dialogue, not just combat. Even if you are travelling as a companion and are mechanically safe from a hostile faction, you still hold your faction's opinions about them."

**Alternatives considered**:
- Per-event injection when companions are present — more complex, marginal benefit
- MCM toggle — over-engineering for a single sentence

**Rationale**: One-line addition to system prompt. Always applies. No runtime cost beyond the static tokens. The note ensures the LLM doesn't ignore faction attitudes just because the companion is mechanically safe.

### Decision 7: Threshold constants as Python module-level dicts

**Choice**: Define `FACTION_THRESHOLDS` and `GOODWILL_TIERS` as module-level constants in `prompts/factions.py`.

**Rationale**: Co-located with `resolve_faction_name()` and `get_faction_description()`. Easy to test. Constants match the engine thresholds from `game_relations.script` exactly.

## Risks / Trade-offs

- **[Stale data]** → Faction matrix is fetched per-event via `query.world`. If relations change mid-dialogue-generation (unlikely in practice), the prompt uses slightly outdated data. Mitigation: acceptable given relations change infrequently.
- **[Token budget]** → Full matrix + goodwill adds ~250–350 tokens per event message. Mitigation: already within the existing prompt token budget; filtering to relevant factions reduces actual injection to ~80–120 tokens for typical events.
- **[Engine API stability]** → `relation_registry.community_relation()` and `actor:community_goodwill()` are stable X-Ray engine APIs used by other mods. Low risk of breakage.
- **[Faction ID mismatch]** → Some faction IDs use `actor_` prefix in engine contexts (e.g., `actor_stalker` for player). Mitigation: Lua's `build_faction_matrix()` strips the `actor_` prefix, consistent with existing `get_faction()` in `talker_game_queries.script`.
