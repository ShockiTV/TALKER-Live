## ADDED Requirements

### Requirement: CooldownManager class exists

The system SHALL provide `domain/service/cooldown.lua` exporting a CooldownManager factory. A CooldownManager instance manages one or more named timer slots and supports configurable cooldown duration, optional anti-spam duration, and the existing 3-mode system (On=0, Off=1, Silent=2).

#### Scenario: Module loads without engine
- **WHEN** `require("domain.service.cooldown")` is called outside the STALKER engine
- **THEN** the module loads successfully

#### Scenario: Create simple cooldown
- **WHEN** `Cooldown.new({ cooldown_ms = 90000 })` is called
- **THEN** a CooldownManager instance is returned with no anti-spam layer

#### Scenario: Create cooldown with anti-spam
- **WHEN** `Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })` is called
- **THEN** a CooldownManager instance is returned with both cooldown and anti-spam layers

### Requirement: check() returns 3-value silence status

The `check(slot_name, current_time, mode)` method SHALL return one of three values matching the existing convention:
- `nil` — abort (anti-spam triggered)
- `true` — silent (cooldown active or mode==Silent)
- `false` — speak (cooldown elapsed and mode==On)

#### Scenario: Mode Off aborts
- **WHEN** `cd:check("default", 1000, 1)` is called with mode=1 (Off)
- **THEN** it returns `nil`

#### Scenario: Mode Silent returns true
- **WHEN** `cd:check("default", 1000, 2)` is called with mode=2 (Silent)
- **THEN** it returns `true`

#### Scenario: Cooldown not elapsed returns true
- **WHEN** cooldown_ms is 90000
- **AND** last check for "default" slot was at time 1000
- **AND** `cd:check("default", 50000, 0)` is called (only 49s elapsed)
- **THEN** it returns `true` (silent — cooldown not elapsed)

#### Scenario: Cooldown elapsed returns false
- **WHEN** cooldown_ms is 90000
- **AND** last check for "default" slot was at time 1000
- **AND** `cd:check("default", 100000, 0)` is called (99s elapsed)
- **THEN** it returns `false` (speak — cooldown elapsed)

#### Scenario: Timer reset on speak
- **WHEN** `cd:check("default", 100000, 0)` returns `false` (speak)
- **AND** `cd:check("default", 100001, 0)` is called immediately after
- **THEN** it returns `true` (silent — cooldown just reset)

### Requirement: Named timer slots are independent

Each named slot SHALL maintain its own independent timer state. Using different slot names SHALL not interfere with each other.

#### Scenario: Two independent slots
- **WHEN** cooldown_ms is 5000
- **AND** `cd:check("player", 1000, 0)` returns `false`
- **AND** `cd:check("npc", 2000, 0)` returns `false`
- **AND** `cd:check("player", 4000, 0)` is called (3s since player, 2s since npc)
- **THEN** it returns `true` (player cooldown not elapsed)

#### Scenario: NPC slot independent from player
- **WHEN** following the same setup as above
- **AND** `cd:check("npc", 8000, 0)` is called (6s since npc)
- **THEN** it returns `false` (npc cooldown elapsed)

### Requirement: Anti-spam layer blocks all registration

When `anti_spam_ms` is configured, the anti-spam check SHALL execute BEFORE the cooldown check. If anti-spam triggers, the event SHALL be completely aborted (return `nil`), not registered as silent.

#### Scenario: Anti-spam blocks event
- **WHEN** anti_spam_ms is 5000
- **AND** last event for slot "pickup" was at time 1000
- **AND** `cd:check("pickup", 3000, 0)` is called (2s since last)
- **THEN** it returns `nil` (abort — anti-spam)

#### Scenario: Anti-spam passes, cooldown blocks
- **WHEN** anti_spam_ms is 5000, cooldown_ms is 60000
- **AND** last event at time 1000
- **AND** `cd:check("pickup", 10000, 0)` is called (9s since last)
- **THEN** anti-spam passes (9s > 5s)
- **AND** cooldown blocks (9s < 60s)
- **AND** it returns `true` (silent)

#### Scenario: Both layers pass
- **WHEN** anti_spam_ms is 5000, cooldown_ms is 60000
- **AND** last event at time 1000
- **AND** `cd:check("pickup", 70000, 0)` is called (69s since last)
- **THEN** it returns `false` (speak)

### Requirement: Configurable on-cooldown behavior

The CooldownManager SHALL support a configurable `on_cooldown` behavior to handle the behavioral difference between trigger scripts:
- `"silent"` (default) — returns `true` when cooldown is active (event registered as silent)
- `"abort"` — returns `nil` when cooldown is active (event completely dropped)

#### Scenario: Default on_cooldown is silent
- **WHEN** `Cooldown.new({ cooldown_ms = 5000 })` is created (no on_cooldown specified)
- **AND** cooldown is still active
- **THEN** `check()` returns `true`

#### Scenario: Abort on_cooldown drops event
- **WHEN** `Cooldown.new({ cooldown_ms = 5000, on_cooldown = "abort" })` is created
- **AND** cooldown is still active
- **THEN** `check()` returns `nil`
