## Context

The `pointer-based-dialogue-messages` spec was synced from the `deduplicated-prompt-architecture` change and mandates that picker/dialogue user messages reference events by `EVT:{ts}` instead of inlining full descriptions. The current implementation diverges:

1. `serialize_event()` in `serializer.lua` drops the `ts` field — Python never receives it on the `game.event` topic
2. `build_event_description()` inlines a multi-line text block with no identifier
3. `build_witness_text()` produces a one-liner with no `ts`
4. Witness events are fetched only for the chosen speaker, after the picker step — the picker sees zero event history
5. The triggering event is rendered separately from the witness event list despite being in it (Lua fans out before publishing)

The Lua-side `memory_store_v2:store_event()` already stores `ts` and returns it in state query responses. The triggering event is already present in each witness's event store by the time Python queries.

## Goals / Non-Goals

**Goals:**
- Serialize `ts` in wire-format event payloads so Python receives the triggering event's timestamp
- Fetch witness events for all candidates in one batch before the picker step
- Deduplicate events across candidates by `ts`, annotate with witness names
- Format all events (including the trigger) in a unified `[ts]` format with witness annotations
- Picker and dialogue steps reference the triggering event by `EVT:{ts}` (completing the pointer spec)
- Event list is ephemeral in both steps — injected before LLM call, removed after (only assistant response persists in dialogue step)

**Non-Goals:**
- Changing the Lua-side event storage format (already has `ts`)
- Changing how fanout or `_inject_witness_events()` works post-dialogue
- Short/sequential event IDs (raw `ts` is used directly)
- Moving event lists into the cached context block (they remain ephemeral per-turn)
- Changing the four-layer message structure

## Decisions

### Decision 1: Add `ts` to `serialize_event()`

One line added to `bin/lua/infra/ws/serializer.lua`:

```lua
return {
    type         = event.type,
    context      = M.serialize_context(event.context),
    game_time_ms = event.game_time_ms,
    ts           = event.ts,          -- ← ADD
    world_context = event.world_context,
    witnesses    = witnesses,
    flags        = event.flags,
}
```

This makes `ts` available on the `game.event` topic payload. State queries already return `ts` (raw memory, no serialization).

### Decision 2: Fetch events for all candidates before picker

Move the `query.memory.events` batch query from after-picker (single speaker) to before-picker (all candidates). Single roundtrip with N sub-queries:

```python
# Before picker, in handle_event():
ev_batch = BatchQuery()
for cand in candidates:
    cid = str(cand.get("game_id", ""))
    ev_batch.add(f"events_{cid}", "query.memory.events",
                 params={"character_id": cid})
ev_result = await self.state_client.execute_batch(ev_batch, timeout=10.0)

# Result: {cand_id: [event_dicts...], ...}
events_by_candidate = {}
for cand in candidates:
    cid = str(cand.get("game_id", ""))
    if ev_result.ok(f"events_{cid}"):
        events_by_candidate[cid] = ev_result[f"events_{cid}"]
```

**Rationale**: One extra roundtrip for ~3-6 candidates is negligible vs. LLM latency. The picker gets richer context for speaker selection, and we avoid a second roundtrip after picking.

### Decision 3: Deduplicate and format events with `ts` and witness annotations

New helper function `assemble_event_list()`:

```python
def assemble_event_list(
    events_by_candidate: dict[str, list[dict]],
    candidate_names: dict[str, str],  # cand_id → name
) -> tuple[dict[int, dict], dict[int, set[str]]]:
    """Deduplicate events across candidates by ts.
    
    Returns:
        unique_events: {ts: event_dict} — deduplicated, sorted by ts
        witness_map: {ts: {name1, name2, ...}} — which candidates saw it
    """
```

Formatting helper `format_event_line()`:

```python
def format_event_line(ts: int, event: dict, witness_names: set[str]) -> str:
    """Format: [ts] TYPE — actor verb victim (witnesses: Name1, Name2)"""
```

Example output:
```
[1709912001] DEATH — Freedom Soldier killed Monolith Fighter (witnesses: Echo, Wolf)
[1709912078] CALLOUT — Duty Soldier spotted Stalker Newbie (witnesses: Echo)
[1709912345] DEATH — Duty Soldier killed Loner Stalker (witnesses: Echo, Wolf, Fanatic)
```

### Decision 4: Picker uses event list + ts pointer

The picker user message becomes:

```
{dynamic_world_line}

**Recent events in area:**
[1709912001] DEATH — Freedom killed Monolith (witnesses: Echo, Wolf)
[1709912345] DEATH — Duty killed Loner (witnesses: Echo, Wolf, Fanatic)

React to event [1709912345].
Candidates: 12345, 67890, 11111
Pick the character who would most naturally react. Respond with ONLY their character ID.
```

All events from the union are shown. The picker can see who witnessed what, informing a better choice.

Picker messages remain ephemeral (injected and removed).

### Decision 5: Dialogue uses speaker's events + ts pointer

The dialogue user message becomes:

```
{dynamic_world_line}

**Recent events witnessed by Echo:**
[1709912001] DEATH — Freedom killed Monolith (witnesses: Echo, Wolf)
[1709912345] DEATH — Duty killed Loner (witnesses: Echo, Wolf, Fanatic)

React to event [1709912345] as **Echo** (ID: 12345).

**Personal memories:**
{narrative}

Generate Echo's dialogue — just the spoken words, nothing else.
```

Only the chosen speaker's events are shown (filtered by `filter_events_for_speaker` or by their `events_by_candidate[speaker_id]` list). The event list is **ephemeral** — injected into the user message before the LLM call; after the call, only the assistant response persists in `_messages`.

**Change from current**: Currently both the user message and assistant response persist. Now only the assistant response persists.

### Decision 6: Ephemeral user messages, persistent assistant responses

Both picker and dialogue steps inject ephemeral user messages. The dialogue step differs from the picker only in that the assistant response is kept:

```python
# Dialogue step:
self._messages.append(user_msg)           # ephemeral
response = await llm_client.complete(self._messages)
self._messages.pop()                      # remove user message
self._messages.append(Message(role="assistant", content=response))  # keep response
```

This keeps the uncacheable dialogue tail minimal — just assistant response lines, no event instruction bloat. Aligns with the `prompt-compaction-strategy` design.

### Decision 7: Remove `build_event_description()` from dialogue path

The inline event description (multi-line `Event: TYPE / Actor: X / Victim: Y`) is no longer needed for the dialogue step. The triggering event appears in the event list with its `ts`, and the instruction references it by `[ts]`.

`build_event_description()` in `picker.py` is generalized or replaced by `format_event_line()`. The picker also uses the `[ts]` format.

## Risks / Trade-offs

**[Risk] Raw `ts` values are large integers** → LLMs handle numeric tokens fine. Raw `ts` is slightly more tokens than a sequential `[E1]` label, but avoids a mapping layer. Acceptable.

**[Trade-off] Fetching events for all candidates adds batch query size** → Typically 3-6 candidates × up to 100 events each. State queries return raw Lua tables (fast, no DB). Single roundtrip. Well within latency budget.

**[Trade-off] Picker sees all candidates' events union** → More tokens in picker prompt, but richer context for better speaker selection. Most events are shared across candidates (they're in the same area), so dedup keeps it manageable.

**[Risk] Triggering event might not yet be in memory when queried** → Verified: Lua fans out to all witnesses BEFORE publishing to Python. The event IS in memory by the time Python queries.

**[Trade-off] Ephemeral user messages in dialogue** → Removes conversational continuity for the LLM (it can't see what instruction it responded to in prior turns). But prior event context is already captured in compacted memories. The assistant responses provide the LLM with sufficient context to avoid repeating itself.
