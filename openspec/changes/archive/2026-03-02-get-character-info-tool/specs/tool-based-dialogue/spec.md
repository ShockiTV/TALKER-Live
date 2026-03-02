## ADDED Requirements

### Requirement: get_character_info tool in tool set

The ConversationManager SHALL include `get_character_info` as a third tool in the TOOLS list, alongside `get_memories` and `background`.

#### Scenario: Three tools available to LLM
- **WHEN** the ConversationManager starts a tool-calling conversation
- **THEN** the LLM SHALL receive three tool definitions: `get_memories`, `background`, and `get_character_info`

#### Scenario: get_character_info dispatched in tool loop
- **WHEN** the LLM returns a tool call for `get_character_info` during the tool loop
- **THEN** the ConversationManager SHALL dispatch it to `_handle_get_character_info` via the `_tool_handlers` registry
- **AND** SHALL append the result as a `Message.tool_result()` before the next LLM call

## MODIFIED Requirements

### Requirement: Tool definitions

The ConversationManager SHALL provide three tools to the LLM:

1. **`get_memories`**: Required param `character_id` (string). Optional param `tiers` (array of strings). Returns structured memory tiers for the NPC. Python fetches from Lua via `state.query.batch`, translates technical fields to human-readable, and returns formatted result.

2. **`background`**: Required params `character_id` (string), `action` ("read"|"write"|"update"). For "write": requires `content` (traits, backstory, connections). For "update": requires field + operators. Reads/writes via `state.query.batch`/`state.mutate.batch`.

3. **`get_character_info`**: Required param `character_id` (string). Returns character info (name, faction, rank, gender, background) plus squad members with the same fields. Side-effect: creates memory entries for new squad members. Used when the LLM needs squad composition or background context for a character.

The existing `GET_BACKGROUND_TOOL` (read-only) SHALL be replaced by this full `BACKGROUND_TOOL`.

#### Scenario: get_memories tool called for speaker
- **WHEN** LLM calls `get_memories(character_id="12467")`
- **THEN** Python SHALL query `memory.events`, `memory.summaries`, `memory.digests`, `memory.cores` for character 12467
- **AND** SHALL translate technical fields (faction IDs, location IDs) to human-readable
- **AND** SHALL return structured tiers object

#### Scenario: get_memories with from_timestamp for diff read
- **WHEN** LLM calls `get_memories(character_id="12467", from_timestamp=340)`
- **THEN** only items with timestamp/end_ts >= 340 SHALL be returned

#### Scenario: background write tool creates new background
- **WHEN** LLM calls `background(character_id="12467", action="write", content={traits: [...], backstory: "...", connections: [...]})`
- **THEN** Python SHALL send `state.mutate.batch` with `set` operation on `memory.background`

#### Scenario: background read tool returns existing background
- **WHEN** LLM calls `background(character_id="12467", action="read")`
- **THEN** Python SHALL query `memory.background` and return the result (or null)

#### Scenario: background update tool modifies fields
- **WHEN** LLM calls `background(character_id="12467", action="update", field="connections", value=[...])`
- **THEN** Python SHALL send `state.mutate.batch` with an `update` operation on `memory.background`

#### Scenario: get_character_info tool returns character with squad
- **WHEN** LLM calls `get_character_info(character_id="12467")`
- **THEN** Python SHALL query `query.character_info` via `state.query.batch`
- **AND** SHALL return `{character: {..., gender, background}, squad_members: [...]}`
