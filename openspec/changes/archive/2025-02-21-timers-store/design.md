## Context

Two timer values are persisted via inline `save_state`/`load_state` callbacks in game scripts, bypassing the centralized `domain/repo/` architecture:

1. **`game_time_since_last_load`** in `talker_game_queries.script` — a cumulative millisecond counter that makes `get_game_time_ms()` survive save/load cycles. Every timestamp in the system flows through this value.
2. **`last_check_time_ms`** in `talker_trigger_idle_conversation.script` — a bookmark tracking when the idle check last ran, used for rate-limiting the 10-second poll interval.

All other persistent state lives in `bin/lua/domain/repo/` modules and is managed centrally by `talker_game_persistence.script`. These two inline stores are the last holdouts.

## Goals / Non-Goals

**Goals:**
- Create `bin/lua/domain/repo/timers.lua` holding both timer values with the standard envelope persistence pattern
- Wire it into `talker_game_persistence.script` under `saved_data.timers` with `timers_version` envelope
- Remove inline `save_state`/`load_state` callbacks from both game scripts
- Maintain exact runtime behavior: game time accumulator survives save/load, idle cooldown resets on load
- Provide legacy migration bridge for old top-level save keys

**Non-Goals:**
- Generic key-value store for arbitrary trigger state (only these two known timers)
- Persisting `last_idle_conversation_time_ms` (intentionally volatile — resets on load to prevent immediate idle conversations)
- Adding versioning migration beyond v0→v1 (the data is trivial)

## Decisions

### 1. Single `timers.lua` module for both values

**Rationale**: Both values are the same anti-pattern (single numeric timestamp persisted inline), both are timer/counter data, and consolidating them into one module avoids creating two near-identical repo files. The module is a natural extension point if more timers need persistence later.

**Alternative considered**: Two separate modules (`game_time_store.lua`, `idle_timer_store.lua`) — rejected because it doubles the boilerplate for two integers that share the same persistence lifecycle.

### 2. Module-level functions (not a class/metatable)

**Rationale**: Matches the `levels.lua` pattern. The timers store is a singleton with trivial state — no need for OOP overhead. Functions: `get_game_time_accumulator()`, `get_idle_last_check_time()`, `set_idle_last_check_time(v)`, `clear()`, `get_save_data(current_game_time_ms)`, `load_save_data(saved_data)`.

No `set_game_time_accumulator()` — the accumulator is set once on load and is read-only during gameplay. The only mutation happens at save time via the `current_game_time_ms` parameter to `get_save_data()`.

### 3. `get_save_data(current_game_time_ms)` accepts the snapshot from the persistence script

**Rationale**: The game time accumulator's saved value must be the *cumulative* time at the moment of save (`time_global() + stored_accumulator`). Rather than having the store depend on `time_global()` or requiring the queries script to update the store before save, the persistence script calls `talker_game_queries.get_game_time_ms()` and passes the result into `get_save_data()`. This keeps the store a pure data container with no game engine dependency. The idle check time is stored as-is (no computation needed).

**Alternative considered**: (A) Queries script registers a save callback to update the store before persistence runs — rejected due to callback ordering dependency. (B) Store calls `time_global()` itself — rejected because repo modules must not depend on game APIs.

### 4. Save key: `saved_data.timers` with `timers_version = 1` envelope

**Rationale**: Follows the naming pattern in `talker_game_persistence.script` where each store gets a top-level key (`compressed_memories`, `events`, `personalities`, `backstories`, `levels`). The envelope: `{ timers_version = 1, timers = { game_time_accumulator = N, idle_last_check_time = N } }`.

### 5. Legacy migration bridge in `talker_game_persistence.script`

**Rationale**: The old keys (`game_time_since_last_load`, `talker_idle_last_check_time_ms`) are top-level on `saved_data`, not inside a `timers` sub-table. The persistence script can see these keys and construct a legacy object to pass to `timers.load_save_data()`, following the same pattern used for the levels store legacy migration. Inside `load_save_data`, a missing `timers_version` triggers the legacy path mapping old keys to new internal names.

### 6. `talker_game_queries.script` has a read-only dependency on the store

**Rationale**: After extraction, `get_game_time_ms()` becomes `return time_global() + timers.get_game_time_accumulator()`. The queries script requires the timers store but never writes to it. Its `save_state`/`load_state` callbacks and `on_game_start` registration for those callbacks are removed entirely.

### 7. `talker_trigger_idle_conversation.script` uses getter/setter

**Rationale**: The trigger script reads `idle_last_check_time` on each tick and writes it when the check interval elapsed. It requires the timers store and calls `get_idle_last_check_time()` / `set_idle_last_check_time(v)`. Its `save_state`/`load_state` callbacks and their `on_game_start` registration are removed. The `load_state` callback's reset of `last_idle_conversation_time_ms` moves to the trigger's existing `on_game_start` (or an equivalent init path), since that variable is volatile and not stored.

## Risks / Trade-offs

**[Game time accumulator is high-coupling]** → Mitigated by keeping the computation logic (`time_global() + accumulator`) in `talker_game_queries.script`. Only the persistence of the raw accumulator value moves. The public API `get_game_time_ms()` is unchanged.

**[Callback ordering on load]** → The persistence script's `load_state` runs as one callback. It loads the timers store before anything else tries to use `get_game_time_ms()`. Since `talker_game_queries` no longer registers its own `load_state`, there's no race.

**[Backward compatibility]** → Legacy bridge in persistence handles old saves. One-time migration: if `saved_data.timers` is nil but old top-level keys exist, they're passed through to `load_save_data` as a legacy object.

**[Extra require in game scripts]** → Negligible. Lua `require` caches after first load. Both scripts already do `package.path` setup.
