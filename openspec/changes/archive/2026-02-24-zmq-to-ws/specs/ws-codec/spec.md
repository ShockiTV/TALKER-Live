# ws-codec

## Purpose

JSON envelope encode/decode for the WebSocket wire format. Translates between Lua tables and the `{t, p, r, ts}` string envelope. Fully pure — no I/O, no game dependencies.

## Requirements

### Requirement: Encode a message envelope

`codec.encode(t, p, r)` SHALL return a JSON string with keys `t` (topic string), `p` (payload table serialized to JSON object), and optionally `r` (request ID string) and `ts` (current time in milliseconds as integer). `r` is omitted when nil. `ts` is always included.

#### Scenario: Encode without request ID

- **WHEN** `codec.encode("game.event", {type="DEATH"})` is called
- **THEN** a JSON string `{"t":"game.event","p":{"type":"DEATH"},"ts":<n>}` is returned
- **AND** no `r` key is present

#### Scenario: Encode with request ID

- **WHEN** `codec.encode("state.query.batch", {queries={}}, "req-1")` is called
- **THEN** the returned JSON string contains `"r":"req-1"`

### Requirement: Decode an incoming envelope

`codec.decode(raw)` SHALL parse `raw` (JSON string) and return a table `{t, p, r, ts}`. If `raw` is not valid JSON or the `t` field is missing, it SHALL return `nil` and an error string.

#### Scenario: Decode valid envelope

- **WHEN** `codec.decode('{"t":"dialogue.display","p":{"speaker_id":"1","dialogue":"Hello"},"ts":100}')` is called
- **THEN** a table with `t = "dialogue.display"` and `p.speaker_id = "1"` is returned

#### Scenario: Decode missing t field returns nil

- **WHEN** `codec.decode('{"p":{},"ts":100}')` is called
- **THEN** `nil` is returned as the first value
- **AND** an error string is returned as the second value

#### Scenario: Decode invalid JSON returns nil

- **WHEN** `codec.decode("not json")` is called
- **THEN** `nil` is returned as the first value

### Requirement: Round-trip fidelity

Encoding a table and then decoding the result SHALL produce a table equal to the original payload.

#### Scenario: Round-trip preserves nested payload

- **WHEN** `codec.decode(codec.encode("t", {a=1, b={c=2}}))` is invoked
- **THEN** `result.p.a == 1` and `result.p.b.c == 2`
- **AND** `result.t == "t"`
