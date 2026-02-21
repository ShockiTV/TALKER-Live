## MODIFIED Requirements

### Requirement: Event Creation Without World Context

The system SHALL create events without a world_context field.

Trigger scripts SHALL delegate business logic (cooldown checks, importance classification) to `bin/lua/` domain modules rather than implementing them inline. The trigger scripts SHALL retain only engine callback registration, engine data fetching, and event wiring.

#### Scenario: Create death event without world_context
- **WHEN** trigger creates DEATH event via Event.create
- **THEN** event contains type, context, game_time_ms, witnesses, flags
- **AND** event does NOT contain world_context field
- **AND** cooldown check is performed via `domain.service.cooldown` CooldownManager
- **AND** importance check is performed via `domain.service.importance` module

#### Scenario: Create artifact event with cooldown delegation
- **WHEN** artifact trigger fires
- **THEN** cooldown/anti-spam check is performed via CooldownManager with slots "pickup", "use", "equip"
- **AND** the event is created only if cooldown allows it

#### Scenario: Interface layer does not query world context
- **WHEN** interface.lua processes an event trigger
- **THEN** it does NOT call query.describe_world()
- **AND** passes nil or omits world_context parameter
