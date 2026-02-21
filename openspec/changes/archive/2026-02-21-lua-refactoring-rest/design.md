## Context

The `engine-facade-testable-lua` change (separate, parallel change) makes `bin/lua/` modules loadable outside the game engine by wrapping globals behind an `interface/engine.lua` facade. This change builds on that foundation by extracting ~750 lines of testable business logic from `gamedata/scripts/` into `bin/lua/` modules. The target scripts total ~5,200 lines across 29 files, containing ~100 extractable functions (33 pure business logic, 67 mixed). After extraction, the scripts become thin engine adapters that delegate decisions to testable domain modules.

Current state of the business logic embedded in scripts:
- **`talker_game_queries.script`** (992 lines) — contains 26 extractable functions including pure data tables (~200 lines of NPC IDs, mutant name mappings, rank/reputation lookups), utility functions, and world description builders
- **6 trigger scripts** — each implement near-identical cooldown logic with slight variations (1-layer vs 2-layer, single vs multi-timer), totaling ~250 lines of duplicated patterns
- **`talker_zmq_query_handlers.script`** (629 lines) — contains 4 serialization functions for wire-format conversion, plus query pipeline logic

## Goals / Non-Goals

**Goals:**
- Extract all pure business logic from `gamedata/scripts/` into testable `bin/lua/` modules
- Eliminate cooldown timer duplication across 6 trigger scripts with a generic CooldownManager
- Move domain data (NPC lists, mutant names, rank/reputation tables) out of the 992-line queries script
- Make serialization functions independently testable
- Keep `gamedata/scripts/` as thin engine adapters — only engine API calls and callback registration remain
- All extracted modules have dedicated test files
- No behavioral changes — extracted logic produces identical results

**Non-Goals:**
- Changing the ZMQ wire protocol or message format (Python service is unaffected)
- Extracting engine-only functions (those that ONLY wrap game API calls stay in scripts)
- Extracting ZMQ bridge/subscriber code (LuaJIT FFI — fundamentally untestable in standard Lua 5.1)
- Adding new features or changing game behavior
- Full test coverage of trigger script orchestration (the engine callback wiring remains untestable)

## Decisions

### 1. CooldownManager as a class with named timers

**Decision**: Create `domain/service/cooldown.lua` as a factory that returns CooldownManager instances. Each instance manages named timer slots (e.g., "player", "npc", "pickup", "damage"). Supports optional anti-spam layer.

```lua
local Cooldown = require("domain.service.cooldown")

-- Simple single-timer (death npc, injury)
local cd = Cooldown.new({ cooldown_ms = 90000 })
local is_silent = cd:check("default", current_time, mode)

-- Multi-timer with anti-spam (artifact)
local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
local is_silent = cd:check("pickup", current_time, mode)
```

The `check(slot_name, current_time, mode)` method returns:
- `nil` — abort (anti-spam triggered or mode==Off)
- `true` — silent (cooldown active or mode==Silent)
- `false` — speak (cooldown elapsed and mode==On)

This matches the existing 3-value return convention used by all trigger scripts.

**Alternatives considered**:
- (A) Single function with config table — works but doesn't encapsulate timer state, callers would need to pass timer tables around
- (B) Separate functions per pattern (simple/two-layer) — still duplicates the mode logic
- **(C) Chosen**: Class with named slots — one implementation, timer state is internal, anti-spam is opt-in via constructor config

**Rationale**: The 5 existing implementations share identical control flow (mode check → anti-spam check → cooldown check → timer reset) but differ in: number of timer slots, presence of anti-spam, and cooldown durations. A class with named slots handles all variants. The `current_time` parameter is injected rather than reading `get_game_time_ms()` internally, making it trivially testable.

### 2. Domain data modules as static tables in `domain/data/`

**Decision**: Create a new `domain/data/` directory for pure Lua data that's currently embedded in scripts:

| Module | Source | Content |
|--------|--------|---------|
| `domain/data/unique_npcs.lua` | `important_npcs` in `talker_game_queries.script` (L656-L832) | Set of ~120 story IDs |
| `domain/data/mutant_names.lua` | `patternToNameMap` in `describe_mutant()` (L175-L228) | Pattern→name mapping table |
| `domain/data/ranks.lua` | `get_rank_value()` + `get_reputation_tier()` | Rank name→value map + reputation thresholds |

**Alternatives considered**:
- Put data in `infra/STALKER/` — wrong layer; this is domain knowledge, not infrastructure
- Merge into existing entity modules (e.g., add to `character.lua`) — conflates data with entity behavior
- **(Chosen)** Dedicated `domain/data/` — pure data modules with no dependencies, easy to test and reference

**Rationale**: These are static lookup tables that never change at runtime. Separating them from the 992-line queries script makes them independently referenceable. The `domain/data/` convention is consistent with `domain/model/` and `domain/repo/`.

### 3. Serializer as stateless module in `infra/zmq/`

**Decision**: Extract `serialize_character`, `serialize_context`, `serialize_event`, `serialize_events` to `infra/zmq/serializer.lua`. The module depends only on table manipulation — no engine globals, no external requires.

**Rationale**: These 4 functions are pure data transformation (Lua table → wire-format table). They're used only by `talker_zmq_query_handlers.script` today but logically belong with the ZMQ infrastructure. Placing them in `infra/zmq/` follows the existing directory structure (`bridge.lua`, `publisher.lua`).

### 4. World description: split pure assembly from engine data fetching

**Decision**: Create `interface/world_description.lua` with a pure `build_description(params)` function that takes resolved values:

```lua
-- Pure function in bin/lua/interface/world_description.lua
function M.build_description(location, time_of_day, weather, shelter_status, campfire_status)
    -- String assembly only — no engine calls
end

-- Pure function
function M.time_of_day(hour)
    -- hour → "morning"/"noon"/"evening"/"night"
end
```

The engine data fetching (`level.rain_factor()`, `level_weathers.get_weather_manager()`, etc.) stays in `talker_game_queries.script` via the engine facade, which calls `build_description()` with resolved values.

**Alternatives considered**:
- Extract everything including engine calls — violates the rule that `bin/lua/` never calls engine APIs directly
- Keep it all in the script — wastes the testable string assembly logic
- **(Chosen)** Split at the data boundary — pure assembly in `bin/lua/`, engine fetching stays in script

### 5. Framework utilities: single `framework/utils.lua` module

**Decision**: Extract `must_exist`, `try`, `join_tables`, `Set`, `shuffle`, `safely`, `array_iter` to `framework/utils.lua`.

**Rationale**: These are generic Lua utilities used across scripts with no TALKER-specific semantics. They belong in the framework layer (which already has `logger.lua` and `inspect.lua`). Keeping them in one file avoids proliferating tiny modules.

### 6. Importance classification in `domain/service/importance.lua`

**Decision**: Extract `is_important_person(character_data, options)` where `options` contains flags like `is_player`, `is_companion`, `is_unique`. The function makes the decision based on pure data rather than querying the engine.

```lua
-- caller resolves engine data, passes pure values
local important = importance.is_important_person({
    is_player = engine.is_player(obj),
    is_companion = engine.is_companion(obj),
    is_unique = engine.is_unique_character_by_id(obj:id()),
    rank = character.experience
})
```

**Rationale**: The current implementation mixes decision logic with engine queries (`queries.is_player()`, `queries.is_companion()`, `queries.is_unique_character_by_id()`). By taking pre-resolved flags, the function becomes a pure predicate testable without any mocks.

### 7. Extraction order: leaf modules first, then consumers

**Decision**: Extract in dependency order:
1. **Phase 1**: Zero-dependency modules — `framework/utils.lua`, `domain/data/*.lua`
2. **Phase 2**: Modules depending on Phase 1 — `domain/service/cooldown.lua`, `domain/service/importance.lua`, `infra/zmq/serializer.lua`
3. **Phase 3**: Modules depending on Phase 2 — `interface/world_description.lua`, `domain/model/character.lua` extensions
4. **Phase 4**: Script refactoring — update scripts to delegate to new modules

**Rationale**: Leaf-first extraction means each module can be tested immediately after creation. Script refactoring comes last because it has the most risk (behavioral changes if extraction is wrong) and depends on all extracted modules being ready.

### 8. Scripts delegate via `require()` using package.path

**Decision**: `gamedata/scripts/` files will `require()` the new `bin/lua/` modules using the standard `package.path` pattern that already exists in all scripts:

```lua
package.path = package.path .. ";./bin/lua/?.lua;"
local cooldown = require("domain.service.cooldown")
local ranks = require("domain.data.ranks")
```

**Rationale**: This pattern is already established in every `talker_*.script` file. The scripts already depend on `bin/lua/` modules (config, logger, domain models). Adding new requires follows the same convention.

## Risks / Trade-offs

**[Risk] Behavioral divergence during extraction** → Extracted logic must produce byte-identical results to the script originals. The cooldown manager is the highest risk because 5 implementations have subtle differences (death returns `true` on cooldown vs injury returns `nil`).
→ Mitigation: Write tests that verify each trigger's calling convention before refactoring. Document the return value contract per trigger. The CooldownManager's `check()` return values must be configurable per instance.

**[Risk] Module load order in game engine** → New `require()` calls in scripts execute at unpredictable load times.
→ Mitigation: All extracted modules are pure Lua with no engine dependencies (they use `interface/engine.lua` facade from the parallel change). They load safely regardless of order.

**[Risk] Performance of `require()` calls in scripts** → Adding requires to hot-path trigger scripts.
→ Mitigation: Lua caches modules after first `require()`. Subsequent calls are a table lookup (~50ns). Not a concern.

**[Trade-off] `domain/data/unique_npcs.lua` becomes stale vs updating both places** → The NPC list in the Lua module must stay in sync with any game mod updates.
→ Mitigation: The existing `important_npcs` list in `talker_game_queries.script` is already manually maintained. Moving it to a dedicated file makes it easier to find and update. Remove the original from the script so there's only one copy.

**[Trade-off] CooldownManager adds abstraction to simple logic** → Individual cooldown functions are ~20 lines each; a class adds a layer.
→ Mitigation: The class eliminates 5× duplication and makes the contract explicit. The API is simpler to use correctly than reimplementing cooldown logic per trigger.
