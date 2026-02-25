# anomaly-trigger-migration

## Purpose

Defines the migration of anomaly detection from XML parsing to a Lua data-table lookup for the anomaly trigger.

## Requirements

### Requirement: Replace load_xml anomaly detection in proximity handler

The `actor_on_feeling_anomaly` handler in `talker_trigger_anomalies.script` SHALL use `is_anomaly_section(section)` (via the engine facade) instead of `queries.load_xml(section)` to determine if a zone section is a known anomaly. The raw section name SHALL be passed as `anomaly_type` in the event context; display name resolution is delegated to the Python service (via `texts/anomaly_sections.py`).

#### Scenario: Known anomaly zone proximity

- **WHEN** the player enters proximity of a zone with section `"zone_mosquito_bald_average"`
- **AND** `is_anomaly_section("zone_mosquito_bald_average")` returns `true`
- **THEN** the anomaly trigger SHALL create an event with `context.anomaly_type = "zone_mosquito_bald_average"`, without calling `queries.load_xml()`

#### Scenario: Unknown zone section ignored

- **WHEN** the player enters proximity of a zone with section `"zone_unknown_custom"`
- **AND** `is_anomaly_section("zone_unknown_custom")` returns `false`
- **THEN** the anomaly trigger SHALL skip event creation (same behavior as when `load_xml` returned empty string)

### Requirement: Replace load_xml anomaly detection in damage handler

The `actor_on_hit_callback` handler in `talker_trigger_anomalies.script` SHALL use `is_anomaly_section(section)` (via the engine facade) instead of `queries.load_xml(section)` to determine if a hit source is a known anomaly. The raw section name SHALL be passed as `anomaly_type` in the event context; display name resolution is delegated to the Python service.

#### Scenario: Known anomaly damages player

- **WHEN** the player is damaged by an entity with section `"zone_field_radioactive_average"`
- **AND** `is_anomaly_section("zone_field_radioactive_average")` returns `true`
- **THEN** the damage handler SHALL create an event with `context.anomaly_type = "zone_field_radioactive_average"`, without calling `queries.load_xml()`

#### Scenario: Non-anomaly damage source ignored

- **WHEN** the player is damaged by an entity with section `"stalker_bandit_01"`
- **AND** `is_anomaly_section("stalker_bandit_01")` returns `false`
- **THEN** the damage handler SHALL skip anomaly event creation (existing NPC damage flow handles this)

### Requirement: No remaining load_xml calls for anomaly detection

After migration, `talker_trigger_anomalies.script` SHALL contain zero calls to `queries.load_xml()`. All anomaly section lookups SHALL go through the anomaly data table.

#### Scenario: Grep verification

- **WHEN** the file `talker_trigger_anomalies.script` is searched for `load_xml`
- **THEN** zero matches SHALL be found
