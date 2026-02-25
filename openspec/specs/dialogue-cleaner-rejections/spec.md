# dialogue-cleaner-rejections

## Purpose

Defines the expanded refusal and rejection detection logic in the dialogue cleaner module.

## Requirements

### Requirement: Expanded refusal detection

The `clean_dialogue()` function in `cleaner.py` SHALL detect LLM refusal responses using a list of at least 20 known refusal substrings. The check SHALL be case-insensitive. When a refusal is detected, the function SHALL return an empty string.

The refusal list SHALL include at minimum the following categories:

**Apology patterns:**
- "I apologize, but I"
- "I'm sorry, but I cannot"
- "I'm sorry, but I can't"

**Inability patterns:**
- "I cannot fulfill"
- "I cannot generate"
- "I cannot complete"
- "I cannot assist with that"
- "I can't fulfill"
- "I can't generate"

**Policy patterns:**
- "safety guidelines"
- "content guidelines"
- "ethical guidelines"
- "usage policies"
- "use-case policy"

**Identity leak patterns:**
- "As an AI"
- "As a language model"
- "AI assistant"
- "openAI"
- "not programmed"
- "against my programming"

**Content block patterns:**
- "prohibited content"
- "inappropriate content"
- "Content is not allowed"
- "Unable to comply"

**Deflection patterns:**
- "If you have any other inquiries"

#### Scenario: Known apology refusal detected

- **WHEN** `clean_dialogue()` receives text containing "I apologize, but I cannot create violent content"
- **THEN** it SHALL return an empty string

#### Scenario: Policy reference detected

- **WHEN** `clean_dialogue()` receives text containing "Due to safety guidelines, I cannot"
- **THEN** it SHALL return an empty string

#### Scenario: Identity leak detected

- **WHEN** `clean_dialogue()` receives text containing "As an AI assistant, I don't have"
- **THEN** it SHALL return an empty string

#### Scenario: Case-insensitive matching

- **WHEN** `clean_dialogue()` receives text containing "as an ai" (lowercase)
- **THEN** it SHALL still detect the refusal and return an empty string

#### Scenario: Normal dialogue passes through

- **WHEN** `clean_dialogue()` receives text like "Hey stalker, watch out for the anomalies ahead."
- **THEN** it SHALL return the cleaned text, not an empty string

#### Scenario: Partial match in legitimate dialogue

- **WHEN** `clean_dialogue()` receives text containing "I apologize for being late to the meeting point"
- **THEN** it SHALL NOT reject the text, because "I apologize, but I" (with comma+but) is NOT present — partial matches of substring fragments SHALL NOT trigger false positives
