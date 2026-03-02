# cooldown-manager (delta)

## MODIFIED Requirements

### Requirement: check() returns 3-value silence status

The `check(slot_name, current_time, mode)` method SHALL return one of three values matching the existing convention:
- `nil` — abort (anti-spam triggered)
- `true` — silent (cooldown active or mode==Silent)
- `false` — speak (cooldown elapsed and mode==On)

The method signature and return semantics are **unchanged**. However, callers SHALL no longer pass `mode=2` (Silent). The consolidated trigger flow uses `mode=0` (On) exclusively — the store-vs-publish decision is made by the caller based on the chance roll result, not by the cooldown manager's mode parameter.

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
