## MODIFIED Requirements

### Requirement: Resource registry maps store.events

The batch handler SHALL maintain a static resource registry mapping resource names to resolver functions. Adding a new resource SHALL require only adding an entry to this registry.

Serialization of resolved data SHALL use `infra.zmq.serializer` module functions instead of inline serialization. The resource resolvers SHALL call `serializer.serialize_event()`, `serializer.serialize_character()`, and `serializer.serialize_events()` from the shared serializer module.

#### Scenario: Resource registry maps store.events
- **WHEN** sub-query has `resource: "store.events"`
- **THEN** registry SHALL map it to `event_store:get_all_events()` as the collection source
- **AND** events SHALL be serialized using `serializer.serialize_events()`

#### Scenario: Resource registry maps store.personalities
- **WHEN** sub-query has `resource: "store.personalities"`
- **THEN** registry SHALL map it to the personalities repo character_personalities map, serialized as `{character_id, personality_id}` collection

#### Scenario: Resource registry maps query.character
- **WHEN** sub-query has `resource: "query.character"` with a `params.character_id`
- **THEN** the resolver SHALL serialize the character using `serializer.serialize_character()`
