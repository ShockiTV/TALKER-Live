## ADDED Requirements

### Requirement: Session-aware generate_from_event

`DialogueGenerator.generate_from_event(event, is_important=False, *, session_id=None)` SHALL accept an optional `session_id` keyword parameter. When provided, the generator SHALL pass `session_id` to all `state.execute_batch()` calls (as `session=session_id`) and all `publisher.publish()` calls (as `session=session_id`). When `None`, behavior SHALL be identical to the current broadcast mode.

#### Scenario: Session_id threads through event generation

- **WHEN** `generate_from_event(event, session_id="player_1")` is called
- **THEN** all state queries SHALL use `session="player_1"`
- **AND** all publish calls (dialogue.display, memory.update) SHALL use `session="player_1"`

#### Scenario: No session_id preserves broadcast behavior

- **WHEN** `generate_from_event(event)` is called without session_id
- **THEN** state queries and publishes SHALL broadcast to all connections

### Requirement: Session-aware generate_from_instruction

`DialogueGenerator.generate_from_instruction(speaker_id, event, *, session_id=None)` SHALL accept an optional `session_id` keyword parameter with the same threading behavior as `generate_from_event`.

#### Scenario: Session_id threads through instruction generation

- **WHEN** `generate_from_instruction("42", event, session_id="player_2")` is called
- **THEN** all state queries and publishes SHALL use `session="player_2"`

### Requirement: Session-aware LLM client access

`DialogueGenerator` SHALL provide a `get_llm(session_id=None)` method. When the generator was constructed with a factory function, `get_llm` SHALL call the factory. If the factory accepts a `session_id` parameter (detected via `inspect.signature`), `session_id` SHALL be passed through. If the factory does not accept `session_id`, it SHALL be called without it (backward compatible). The existing `llm` property SHALL be retained for backward compatibility, delegating to `get_llm(None)`.

#### Scenario: Factory with session_id parameter receives session

- **WHEN** the generator is constructed with a factory `def factory(session_id=...)`
- **AND** `get_llm("session_x")` is called
- **THEN** the factory SHALL receive `session_id="session_x"`

#### Scenario: Zero-arg factory still works

- **WHEN** the generator is constructed with a zero-arg factory `def factory()`
- **AND** `get_llm("session_y")` is called
- **THEN** the factory SHALL be called without arguments

### Requirement: Heartbeat ack targets session

`handle_heartbeat(payload, session_id)` SHALL publish `service.heartbeat.ack` with `session=session_id` so the ack reaches only the requesting player. Config re-request (`config.request`) SHALL also target the specific session.

#### Scenario: Heartbeat ack routed to correct session

- **WHEN** session "player_3" sends a heartbeat
- **THEN** `service.heartbeat.ack` SHALL be published with `session="player_3"`

#### Scenario: Config request targets session on no sync

- **WHEN** session "player_4" sends a heartbeat
- **AND** config is not yet synced for that session
- **THEN** `config.request` SHALL be published with `session="player_4"`
