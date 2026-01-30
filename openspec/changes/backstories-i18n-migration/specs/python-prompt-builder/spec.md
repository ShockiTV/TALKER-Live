# python-prompt-builder delta

## ADDED Requirements

### Requirement: Backstory i18n resolution

The prompt builder SHALL resolve backstory IDs to localized text using python-i18n.

#### Scenario: Resolve unique character backstory ID
- **GIVEN** a character with `backstory_id = "unique.wolf"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("unique.wolf", locale)` is called
- **AND** returns the translated backstory text from JSON

#### Scenario: Resolve generic character backstory ID
- **GIVEN** a character with `backstory_id = "generic.loner.3"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("generic.loner.3", locale)` is called
- **AND** returns the translated backstory text from JSON

#### Scenario: Fallback for missing backstory
- **GIVEN** a character with `backstory_id = "unknown.99"`
- **WHEN** `resolve_backstory("unknown.99", locale)` is called
- **AND** no translation exists
- **THEN** returns empty string

#### Scenario: Locale fallback to English
- **GIVEN** locale is "ru"
- **AND** backstory "unique.wolf" has no Russian translation
- **WHEN** `resolve_backstory("unique.wolf", "ru")` is called
- **THEN** falls back to English translation
