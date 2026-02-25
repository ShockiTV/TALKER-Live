# injury-trigger-guards

## Purpose

Defines guard conditions for the injury trigger to prevent nil-reference errors and handle edge cases.

## Requirements

### Requirement: Nil attacker guard

The `actor_on_hit_callback` in `talker_trigger_injury.script` SHALL return early without creating an event when the `who` parameter is `nil`. This prevents crashes from fall damage, environmental damage, or other sources with no attacker object.

#### Scenario: Fall damage produces nil attacker

- **WHEN** the player takes fall damage and `actor_on_hit_callback` fires with `who = nil`
- **THEN** the callback SHALL return immediately without calling `trigger.talker_event_near_player()`

#### Scenario: Environmental damage produces nil attacker

- **WHEN** the player takes damage from a non-entity source (e.g. scripted damage) and `who` is `nil`
- **THEN** the callback SHALL return immediately without error

### Requirement: Self-damage guard

The `actor_on_hit_callback` SHALL return early when the attacker is the player themselves (`who == db.actor`). This prevents nonsensical injury events from self-inflicted grenade damage.

#### Scenario: Grenade self-damage

- **WHEN** the player damages themselves with their own grenade and `who` is `db.actor`
- **THEN** the callback SHALL return immediately without creating an injury event

### Requirement: Anomaly-source damage guard

The `actor_on_hit_callback` SHALL return early when the attacker's section is a known anomaly section (as defined by the `anomaly-data-table` capability). This prevents duplicate events — the `talker_trigger_anomalies.script` already handles anomaly damage.

#### Scenario: Anomaly zone damages player

- **WHEN** the player is hit by an entity whose `section()` returns `"zone_mosquito_bald_average"` (a known anomaly section)
- **THEN** the callback SHALL return immediately, deferring to the anomaly trigger

#### Scenario: Normal NPC damages player

- **WHEN** the player is hit by an NPC whose section is `"stalker_bandit_01"` (not an anomaly)
- **THEN** the callback SHALL proceed to create an injury event normally

### Requirement: MCM threshold safety

The `actor_on_hit_callback` SHALL guard the MCM `injury_threshold` value with `tonumber()` and a fallback default of `0.4`, since MCM can return string values.

#### Scenario: MCM returns string threshold

- **WHEN** `mcm.get("injury_threshold")` returns the string `"0.5"`
- **THEN** the callback SHALL convert it to the number `0.5` and use it for comparison

#### Scenario: MCM returns nil threshold

- **WHEN** `mcm.get("injury_threshold")` returns `nil`
- **THEN** the callback SHALL fall back to `0.4` as the threshold

### Requirement: Guard ordering

The three guards SHALL be applied in this order before any other logic:
1. Nil check (`who == nil`)
2. Self-damage check (`who == db.actor`)
3. Anomaly check (via `is_anomaly_section`)

This order is deliberate: the nil check must come first (accessing methods on nil crashes), and the self-damage check is cheaper than the anomaly lookup.

#### Scenario: Guards evaluated in correct order

- **WHEN** `who` is `nil`
- **THEN** the nil guard fires first, before attempting `who == db.actor` or `who:section()`
