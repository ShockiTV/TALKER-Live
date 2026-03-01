# config-authority-pins

## Purpose

Server-side `.env` values pin ConfigMirror fields, overriding MCM. Includes pin storage, `.get()` priority, audit logging, startup wiring, OpenAI endpoint override, and backward-compat aliases.

## Requirements

### Pin a config field

The config mirror SHALL allow fields to be pinned to server-side values that override MCM.

#### Scenario: Pin a field before any sync
- **WHEN** `config_mirror.pin("model_method", 3)` is called at startup
- **THEN** subsequent `config_mirror.get("model_method")` returns `3` regardless of MCM values

#### Scenario: Pin overrides MCM update
- **WHEN** `model_method` is pinned to `0`
- **AND** a `config.update` sets `model_method` to `2`
- **THEN** `config_mirror.get("model_method")` still returns `0`

#### Scenario: Pin overrides MCM sync
- **WHEN** `model_method` is pinned to `0`
- **AND** a `config.sync` sets `model_method` to `2`
- **THEN** `config_mirror.get("model_method")` still returns `0`

### Unpinned fields pass through

The config mirror SHALL return MCM values for fields that are not pinned.

#### Scenario: Unpinned field returns MCM value
- **WHEN** `witness_distance` is not pinned
- **AND** MCM sets `witness_distance` to `50`
- **THEN** `config_mirror.get("witness_distance")` returns `50`

### Audit logging for pinned field changes

The config mirror SHALL log when MCM attempts to change a pinned field.

#### Scenario: MCM tries to change pinned field
- **WHEN** `model_method` is pinned to `0`
- **AND** a `config.update` or `config.sync` sends `model_method=2`
- **THEN** the mirror logs at INFO level: the field name, the MCM-attempted value, and the pinned value

#### Scenario: MCM sends same value as pin
- **WHEN** `model_method` is pinned to `0`
- **AND** MCM sends `model_method=0`
- **THEN** no audit log is emitted for that field

### Pinned fields reported in config dump

The config mirror SHALL include pin information in its dump output.

#### Scenario: Dump shows pins
- **WHEN** `config_mirror.dump()` is called
- **AND** `model_method` is pinned to `3`
- **THEN** the dump includes a `pins` key with `{"model_method": 3}`

### LLM provider pin from .env

The Settings model SHALL support `LLM_PROVIDER` env var that pins the LLM provider at startup.

#### Scenario: LLM_PROVIDER set in .env
- **WHEN** `LLM_PROVIDER=openai` is in `.env`
- **THEN** `config_mirror.pin("model_method", 0)` is called at startup

#### Scenario: LLM_PROVIDER absent, FORCE_PROXY_LLM present
- **WHEN** `LLM_PROVIDER` is not set
- **AND** `FORCE_PROXY_LLM=true` is in `.env`
- **THEN** `config_mirror.pin("model_method", 3)` is called at startup

#### Scenario: Neither set
- **WHEN** neither `LLM_PROVIDER` nor `FORCE_PROXY_LLM` is set
- **THEN** `model_method` is not pinned and MCM controls it

### LLM model pin from .env

The Settings model SHALL support `LLM_MODEL` and `LLM_MODEL_FAST` env vars.

#### Scenario: LLM_MODEL set
- **WHEN** `LLM_MODEL=gpt-4o` is in `.env`
- **THEN** `config_mirror.pin("model_name", "gpt-4o")` is called at startup

#### Scenario: LLM_MODEL_FAST set
- **WHEN** `LLM_MODEL_FAST=gpt-4o-mini` is in `.env`
- **THEN** `config_mirror.pin("model_name_fast", "gpt-4o-mini")` is called at startup

### STT method pin from .env

The Settings model SHALL support `STT_METHOD` env var.

#### Scenario: STT_METHOD set
- **WHEN** `STT_METHOD=local` is in `.env`
- **THEN** `config_mirror.pin("stt_method", "local")` is called at startup

#### Scenario: STT_METHOD absent, FORCE_LOCAL_WHISPER present
- **WHEN** `STT_METHOD` is not set
- **AND** `FORCE_LOCAL_WHISPER=true` is in `.env`
- **THEN** `config_mirror.pin("stt_method", "local")` is called at startup

### OpenAI endpoint override

The OpenAI LLM client SHALL support a custom API endpoint.

#### Scenario: OPENAI_ENDPOINT set
- **WHEN** `OPENAI_ENDPOINT=https://models.inference.ai.azure.com/chat/completions` is in `.env`
- **THEN** the OpenAI client sends requests to that URL instead of `api.openai.com`

#### Scenario: OPENAI_ENDPOINT absent
- **WHEN** `OPENAI_ENDPOINT` is not set
- **THEN** the OpenAI client uses `https://api.openai.com/v1/chat/completions`

### Cache clearing respects pins

LLM client cache SHALL only be cleared when effective (post-pin) values change.

#### Scenario: Pinned model_method prevents cache clear
- **WHEN** `model_method` is pinned to `0`
- **AND** MCM sends `model_method=2`
- **THEN** the LLM client cache is NOT cleared

#### Scenario: Unpinned model_method triggers cache clear
- **WHEN** `model_method` is not pinned
- **AND** MCM changes `model_method` from `0` to `2`
- **THEN** the LLM client cache IS cleared
