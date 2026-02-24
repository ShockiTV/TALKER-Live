# ws-schema-validation

## Purpose

Schema compiler that translates the custom YAML format to JSON Schema, plus pytest integration that validates e2e scenario files against the compiled schema.

## Requirements

### Requirement: Schema compiler module

The system SHALL provide a `schema_compiler.py` module in `talker_service/tests/e2e/` that loads `docs/ws-api.yaml` and produces JSON Schema dicts.

The compiler SHALL:
- Load and parse the YAML file
- Translate each type in `types:` to a JSON Schema `$defs` entry
- Translate each message's `payload` (or `request`/`response`) to a JSON Schema object
- Map custom field attributes to JSON Schema equivalents:
  - `type: string` → `{"type": "string"}`
  - `type: int` → `{"type": "integer"}`
  - `type: float` → `{"type": "number"}`
  - `type: bool` → `{"type": "boolean"}`
  - `type: object` → `{"type": "object"}`
  - `type: array` with `items` → `{"type": "array", "items": ...}`
  - `type: any` → `{}` (no type constraint)
  - `required: true` → field added to JSON Schema `required` array
  - `default: <value>` → `{"default": <value>}`
  - `enum: [a, b, c]` → `{"enum": ["a", "b", "c"]}`
  - `$ref: TypeName` → `{"$ref": "#/$defs/TypeName"}`
- Return a dict of `{topic: {"payload": <json_schema>, "request": <json_schema>, "response": <json_schema>}}` keyed by topic name
- Expose a `compile_schema(yaml_path) -> dict` public function

#### Scenario: Compiler produces valid JSON Schema for a message

- **WHEN** `compile_schema("docs/ws-api.yaml")` is called
- **THEN** the returned dict SHALL contain an entry for `"game.event"`
- **AND** the `"payload"` value SHALL be a valid JSON Schema object with `$defs` for referenced types

#### Scenario: Compiler maps custom types to JSON Schema $defs

- **WHEN** the YAML defines `types.Character` with fields `game_id: {type: string, required: true}`
- **THEN** the compiled JSON Schema SHALL include `$defs.Character` with `properties.game_id: {"type": "string"}` and `"game_id"` in the `required` array

#### Scenario: Compiler handles $ref fields

- **WHEN** a payload field specifies `$ref: Character`
- **THEN** the compiled JSON Schema SHALL produce `{"$ref": "#/$defs/Character"}` for that field

#### Scenario: Compiler handles array fields with typed items

- **WHEN** a payload field specifies `type: array, items: {$ref: Character}`
- **THEN** the compiled JSON Schema SHALL produce `{"type": "array", "items": {"$ref": "#/$defs/Character"}}`

### Requirement: Scenario payload validation at collection time

The system SHALL validate all e2e scenario file payloads against the compiled schema during pytest collection.

Validation SHALL check:
- `input.payload` against the schema for the topic specified in `input.topic`
- Each entry in `state_mocks.<topic>.response` against the response schema for that topic
- Each entry in `expected.ws_published[].payload` against the schema for that entry's `topic`
- Each entry in `expected.state_queries[].payload` against the request schema for that entry's `topic`

#### Scenario: Valid scenario passes schema validation

- **WHEN** a scenario file has `input.topic: "game.event"` and `input.payload` matches the `game.event` payload schema
- **THEN** the scenario SHALL pass schema validation without errors

#### Scenario: Invalid payload field type fails validation

- **WHEN** a scenario file has `input.payload.is_important` set to a string `"yes"` instead of a boolean
- **THEN** schema validation SHALL fail with a descriptive error during test collection
- **AND** the error SHALL identify the field and expected type

#### Scenario: Missing required field fails validation

- **WHEN** a scenario file has `input.topic: "game.event"` but `input.payload.event` is missing
- **THEN** schema validation SHALL fail during test collection
- **AND** the error SHALL identify `event` as a required field

#### Scenario: Validation is tolerant of extra fields

- **WHEN** a scenario payload contains fields not defined in the schema
- **THEN** validation SHALL NOT fail (additionalProperties allowed)
- **AND** this allows for forward-compatible scenario files

### Requirement: jsonschema dependency

The project SHALL add `jsonschema` to `[project.optional-dependencies] dev` in `talker_service/pyproject.toml`.

#### Scenario: jsonschema is available in dev environment

- **WHEN** the dev dependencies are installed via `pip install -e ".[dev]"`
- **THEN** `import jsonschema` SHALL succeed
