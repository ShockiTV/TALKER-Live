## Why

When talker_service is deployed on a shared server, any connected game client can change the LLM provider, model name, or STT method via MCM config sync — causing the server to use expensive models or external APIs on the operator's credentials. The current `FORCE_PROXY_LLM` and `FORCE_LOCAL_WHISPER` flags only cover narrow cases and leave the general problem unsolved.

## What Changes

- ConfigMirror gains a "pinned fields" mechanism: `.env` values override MCM for specific fields, transparently via `.get()`
- New `.env` settings: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_MODEL_FAST`, `STT_METHOD` — when set, MCM cannot change them
- OpenAI client gains `OPENAI_ENDPOINT` support so the operator can use Azure/GitHub Models directly without proxy mode
- Old `FORCE_PROXY_LLM` / `FORCE_LOCAL_WHISPER` kept as backward-compat aliases
- `get_current_llm_client()` and `_init_stt_on_config()` simplified — no more `if force_*` branching, just `config_mirror.get()` which respects pins
- LLM cache clearing skipped when pinned fields prevent effective value changes

## Capabilities

### New Capabilities
- `config-authority-pins`: Server-side `.env` values pin ConfigMirror fields, overriding MCM. Includes pin storage, `.get()` priority, audit logging, and startup wiring.

### Modified Capabilities
- `python-config-mirror`: ConfigMirror gains `pin()` method, `.get()` checks pins before stored config, `update()`/`sync()` log when MCM attempts to change pinned fields, cache clearing is skipped when effective LLM values are unchanged due to pins.

## Impact

- **Python only** — no Lua changes. MCM still sends all fields; server just ignores pinned ones.
- **Files**: `config.py` (Settings), `handlers/config.py` (ConfigMirror), `__main__.py` (startup wiring, factory closure), `llm/openai_client.py` (endpoint override), `.env` / `.env.example`
- **Tests**: New unit tests for pin mechanism, updated tests for config mirror behavior
- **Backward compat**: `FORCE_PROXY_LLM=true` → `LLM_PROVIDER=proxy`, `FORCE_LOCAL_WHISPER=true` → `STT_METHOD=local`
