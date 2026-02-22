## ADDED Requirements

### Requirement: Disguise awareness instructions in dialogue prompt

The dialogue prompt builder SHALL detect when any recent event contains a disguised character (indicated by `[disguised as` in the rendered event text) and conditionally inject DISGUISE AWARENESS and DISGUISE NOTATION instructions into the prompt.

The injected instructions SHALL differentiate between companions (who knew about the disguise) and non-companions (who did not).

The injection SHALL appear after the `</EVENTS>` section and before the context use guidelines.

#### Scenario: Disguise instructions injected when disguise present (non-companion)
- **WHEN** `create_dialogue_request_prompt()` is called with events containing a character with `visual_faction` set
- **AND** the speaker is NOT a companion
- **THEN** the prompt SHALL include a `## DISGUISE CONTEXT` section
- **AND** the section SHALL instruct the LLM that the speaker did NOT know it was a disguise
- **AND** the section SHALL tell the LLM to treat the person by their apparent (disguised) faction

#### Scenario: Disguise instructions injected when disguise present (companion)
- **WHEN** `create_dialogue_request_prompt()` is called with events containing a disguised character
- **AND** `is_companion=True`
- **THEN** the prompt SHALL include a `## DISGUISE CONTEXT` section
- **AND** the section SHALL state the companion was aware of the disguise
- **AND** the section SHALL allow explicit references to the disguise in past tense

#### Scenario: No disguise instructions when no disguise present
- **WHEN** `create_dialogue_request_prompt()` is called with events that have no characters with `visual_faction`
- **THEN** the prompt SHALL NOT include a `## DISGUISE CONTEXT` section
