## Context

The `Character` entity in Lua currently acts as a "god object," mixing raw engine state (health, faction, location) with domain-level narrative concepts (backstory and personality). This coupling bloats ZMQ event payloads because every witness in every event carries full narrative strings. It also creates a risk of stale data if a character's personality changes.

We are moving to a "Lean DTO" pattern where the `Character` object is stripped of narrative data. Instead, Python will fetch these traits on-demand using the `BatchQuery` protocol. To ensure Python always receives valid data, Lua will retain the responsibility of "lazy generation"—if Python queries a trait that doesn't exist, Lua will generate it, save it, and return it.

## Goals / Non-Goals

**Goals:**
- Strip `backstory` and `personality` fields from the `Character` entity in both Lua and Python.
- Remove narrative formatting functions (`describe`, `describe_short`) from the Lua `Character` entity.
- Implement a two-phase fetch in Python's `DialogueGenerator`:
  1. Fetch personalities for all witnesses before picking a speaker.
  2. Fetch the backstory for the chosen speaker before generating dialogue.
- Ensure Lua's `talker_zmq_query_handlers.script` handles lazy generation of missing traits when queried by Python.
- Pass personalities as a simple dictionary to Python prompt builders.

**Non-Goals:**
- Changing the underlying logic of *how* backstories or personalities are generated (just *when* and *where* they are attached).
- Modifying the memory compression system.
- Changing the structure of the `Event` entity beyond the changes to its `witnesses` (which are `Character` objects).

## Decisions

1.  **Lean DTO for Character:**
    *   **Decision:** Remove `backstory` and `personality` from the `Character` object.
    *   **Rationale:** Reduces ZMQ payload size significantly. Separates engine state from narrative state.
    *   **Alternatives:** Keep them but make them optional/lazy-loaded within the object itself. Rejected because it maintains the conceptual coupling and complicates serialization.

2.  **Lua Owns Lazy Generation:**
    *   **Decision:** When Python queries `store.personalities` or `store.backstories` via `BatchQuery`, if the trait is missing, Lua's query handler will generate it, save it to the respective store, and return the new ID.
    *   **Rationale:** Guarantees Python never receives `null` for a trait, simplifying Python's logic. Keeps the generation logic (which relies on Lua-side random seeds and data tables) centralized in Lua.
    *   **Alternatives:** Python handles missing traits by sending a separate "generate" command. Rejected because it adds unnecessary roundtrips and complexity to the Python orchestrator.

3.  **Two-Phase Fetch in Python:**
    *   **Decision:** `DialogueGenerator` will perform two `BatchQuery` calls. First, to get personalities for all witnesses to feed the speaker selection prompt. Second, to get the backstory (and memory) for the chosen speaker to feed the dialogue generation prompt.
    *   **Rationale:** Optimizes data fetching. We don't need backstories for characters who aren't speaking.
    *   **Alternatives:** Fetch everything for everyone upfront. Rejected because it wastes bandwidth and processing time on characters who won't speak.

4.  **Dictionary Passing for Personalities:**
    *   **Decision:** Pass the fetched personalities to the prompt builders as a simple dictionary (`Dict[str, str]`) mapping character IDs to personality IDs/strings.
    *   **Rationale:** Simple, direct, and avoids unnecessary boilerplate object creation just to pass data to the LLM.

## Risks / Trade-offs

-   **[Risk] Increased Latency:** Adding `BatchQuery` roundtrips before dialogue generation could increase the time it takes for an NPC to respond.
    -   **Mitigation:** `BatchQuery` is designed to be fast. The two-phase fetch ensures we only fetch what's strictly necessary. The reduction in initial event payload size might offset some of this latency.
-   **[Risk] Test Breakage:** This is a fundamental change to a core entity. Many tests in both Lua and Python will break.
    -   **Mitigation:** Comprehensive updates to test mocks and fixtures will be required as part of the implementation phase.

## Migration Plan

1.  Update Lua `Character` entity and `game_adapter.lua` to remove traits.
2.  Update Lua `talker_zmq_query_handlers.script` to implement lazy generation.
3.  Update Python `Character` model to match the new Lean DTO.
4.  Update Python `DialogueGenerator` to implement the two-phase fetch.
5.  Update Python prompt builders to accept the new dictionary format.
6.  Fix all broken tests in both codebases.

## Open Questions

-   Are there any edge cases where a character might be queried for a trait *before* they are fully initialized in the game world, leading to incorrect generation? (Likely no, as events only trigger for initialized characters, but worth verifying).
