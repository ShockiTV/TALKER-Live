## MODIFIED Requirements

### Requirement: Aggregate World Context for Prompts

The system SHALL provide `build_world_context(scene_data, recent_events, state_client)` that aggregates all context sections. The aggregated output SHALL include a "Notable Zone Inhabitants" section listing relevant characters with alive/dead annotations, replacing the previously separate dead leaders and dead important characters sections.

#### Scenario: Full world context built with inhabitants
- **WHEN** build_world_context is called with scene_data and alive_status
- **THEN** result SHALL include a "Notable Zone Inhabitants" section listing relevant characters with alive/dead annotations
- **AND** SHALL include info portions section if any disabled
- **AND** SHALL include regional politics section if applicable
- **AND** SHALL NOT include separate dead leaders or dead important characters sections

#### Scenario: Inhabitants section replaces dead character sections
- **WHEN** build_world_context is called and Voronin is dead
- **THEN** Voronin SHALL appear in the "Notable Zone Inhabitants" section annotated "(dead)"
- **AND** there SHALL be no separate "Dead faction leaders" text block in the output

#### Scenario: Empty world context when nothing notable
- **GIVEN** all leaders alive, no info portions, no regional context, no area-matched characters
- **WHEN** build_world_context is called
- **THEN** the inhabitants section SHALL still list leaders (always visible)
- **AND** other sections SHALL be empty or absent

### Requirement: Build Dead Leaders Context

The system SHALL retain `build_dead_leaders_context()` for backward compatibility but it SHALL no longer be called by `build_world_context()`. The Notable Zone Inhabitants section subsumes dead leader reporting.

#### Scenario: Dead leaders context still callable
- **WHEN** `build_dead_leaders_context()` is called directly
- **THEN** it SHALL still return text listing dead faction leaders

#### Scenario: Dead leaders context not included in aggregate
- **WHEN** `build_world_context()` aggregates sections
- **THEN** it SHALL NOT call or include output from `build_dead_leaders_context()`

### Requirement: Build Dead Important Characters Context

The system SHALL retain `build_dead_important_context()` for backward compatibility but it SHALL no longer be called by `build_world_context()`. The Notable Zone Inhabitants section subsumes dead important character reporting.

#### Scenario: Dead important context still callable
- **WHEN** `build_dead_important_context()` is called directly
- **THEN** it SHALL still return text listing dead important characters filtered by area/events

#### Scenario: Dead important context not included in aggregate
- **WHEN** `build_world_context()` aggregates sections
- **THEN** it SHALL NOT call or include output from `build_dead_important_context()`
