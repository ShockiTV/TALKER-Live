# python-prompt-builder (Delta Spec)

## MODIFIED Requirements

### Text Lookup

The system MUST provide `resolve_personality(id)`, `resolve_backstory(id)`, `resolve_faction_name(faction_id)`, and `resolve_reputation_tier(reputation_int)` for ID→text lookup.

#### Storage Format
- Personality and backstory texts are stored as Python dict constants in `.py` modules
- Located at `talker_service/texts/personality/` and `talker_service/texts/backstory/`
- Each faction has its own module (e.g., `bandit.py`, `unique.py`)
- Each module exports a `TEXTS` dict mapping string keys to string values
- Faction names and descriptions are stored in `talker_service/src/talker_service/prompts/factions.py`
- Faction descriptions are keyed by technical faction ID (e.g., "dolg", "killer", "csky")

#### Scenario: Resolve personality ID
- **WHEN** resolve_personality("bandit.3") is called
- **THEN** returns the personality text from bandit.TEXTS["3"]

#### Scenario: Resolve backstory ID  
- **WHEN** resolve_backstory("unique.wolf") is called
- **THEN** returns the backstory text from unique.TEXTS["wolf"]

#### Scenario: Resolve unique character backstory ID
- **GIVEN** a character with `backstory_id = "unique.esc_2_12_stalker_wolf"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("unique.esc_2_12_stalker_wolf")` is called
- **AND** returns the backstory text from texts/backstory/unique.py TEXTS["esc_2_12_stalker_wolf"]

#### Scenario: Resolve faction backstory ID
- **GIVEN** a character with `backstory_id = "loner.3"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("loner.3")` is called
- **AND** returns the backstory text from texts/backstory/loner.py TEXTS["3"]

#### Scenario: Invalid format returns empty string
- **WHEN** resolve_personality is called with text not matching "{faction}.{key}" format
- **THEN** returns empty string

#### Scenario: Resolve faction ID to display name
- **WHEN** resolve_faction_name("dolg") is called
- **THEN** returns "Duty"

#### Scenario: Resolve faction ID mercenary
- **WHEN** resolve_faction_name("killer") is called
- **THEN** returns "Mercenary"

#### Scenario: Resolve faction ID Clear Sky
- **WHEN** resolve_faction_name("csky") is called
- **THEN** returns "Clear Sky"

#### Scenario: Unknown faction ID returns ID itself
- **WHEN** resolve_faction_name("unknown_faction") is called
- **THEN** returns "unknown_faction"

#### Scenario: Resolve visual_faction (disguise) to display name
- **WHEN** character has visual_faction="dolg"
- **THEN** prompt displays "[disguised as Duty]"

#### Scenario: Reputation passed as integer to prompts
- **WHEN** reputation value 1500 is received from Lua
- **THEN** Character.reputation is stored as integer 1500
- **AND** prompt displays numeric value "CURRENT REPUTATION: 1500"

#### Scenario: Negative reputation displayed numerically
- **WHEN** reputation value -2000 is received from Lua
- **THEN** prompt displays numeric value "CURRENT REPUTATION: -2000"
