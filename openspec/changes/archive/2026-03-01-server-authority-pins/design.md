## Context

ConfigMirror receives MCM config from game clients and provides typed access to all service modules. Currently, LLM provider/model selection and STT method are controlled entirely by MCM values. Two narrow `.env` flags (`FORCE_PROXY_LLM`, `FORCE_LOCAL_WHISPER`) exist but only cover specific cases and require scattered `if` branching in `__main__.py` and `handlers/config.py`.

The OpenAI client hardcodes `API_URL = "https://api.openai.com/v1/chat/completions"`, making it impossible to use Azure/GitHub Models endpoints without going through the Proxy client.

## Goals / Non-Goals

**Goals:**
- Server `.env` is the final authority on LLM provider, model, and STT method when the corresponding env var is set
- Pin mechanism is transparent — consumers call `config_mirror.get()` as before, pins are invisible to them
- OpenAI client supports custom endpoints via `OPENAI_ENDPOINT`
- Old `FORCE_PROXY_LLM` / `FORCE_LOCAL_WHISPER` work as backward-compat aliases
- Audit logging when MCM attempts to change a pinned field

**Non-Goals:**
- Stripping MCM options in Lua or preventing them from being sent
- Pinning non-constructor fields (trigger enables, timeouts, etc.) — those are safe for MCM
- A general-purpose field allowlist/denylist system
- TTS provider pinning (no MCM surface for it yet)

## Decisions

### 1. Pin storage in ConfigMirror (not Settings)

Pins live in `ConfigMirror._pins: dict[str, Any]`. The `.get()` method checks pins before the stored MCM config.

**Why not in Settings?** Settings is a pydantic-settings model for `.env` values. Pins are a runtime concern of ConfigMirror — they govern which values `.get()` returns. Keeping them in ConfigMirror means the override logic is in one place, and the rest of the codebase doesn't change at all.

**Alternative considered:** Separate `AuthorityConfig` class that wraps ConfigMirror. Over-engineered for 4 fields.

### 2. New `.env` keys without `FORCE_` prefix

```
LLM_PROVIDER=openai          # openai | openrouter | ollama | proxy
LLM_MODEL=gpt-4o             # model name
LLM_MODEL_FAST=gpt-4o-mini   # fast model (speaker selection)
STT_METHOD=local              # local | api | proxy
```

**Why drop `FORCE_`?** Presence of the key IS the override. If absent, MCM controls. No boolean + value pair needed.

**Backward compat:** If `LLM_PROVIDER` is absent but `FORCE_PROXY_LLM=true`, treat as `LLM_PROVIDER=proxy`. Same for `FORCE_LOCAL_WHISPER=true` → `STT_METHOD=local`.

### 3. OpenAI client endpoint override

`OpenAIClient.__init__` gains `endpoint` parameter, falling back to `OPENAI_ENDPOINT` env var, then the hardcoded default.

**Why?** The operator currently uses proxy mode to reach Azure endpoints. With endpoint override, they can use `LLM_PROVIDER=openai` directly and get proper retry logic, error handling, and model validation — things ProxyClient doesn't have.

### 4. Simplified cache clearing

`update()` and `sync()` compare effective values (after pins) rather than raw MCM values. If `model_method` and `model_name` are pinned, no MCM change can alter the effective values, so the LLM client cache is never cleared unnecessarily.

### 5. Pin wiring at startup in `__main__.py`

Startup code reads `settings.llm_provider`, `settings.llm_model`, etc. and calls `config_mirror.pin()` before any handler registration. This is the single point where authority is established.

The existing `get_current_llm_client()` closure and `_init_stt_on_config()` callback lose all `if force_*` branching — they just call `config_mirror.get()` which transparently returns pinned values.

## Risks / Trade-offs

- **Env var proliferation** → Mitigated: only 4 new keys, all optional. Old keys kept as aliases.
- **Pin hides MCM intent from logs** → Mitigated: `update()`/`sync()` log when MCM sends a value that differs from the pin, e.g. `"MCM wants model_method=2, pinned to 0 — ignored"`
- **OpenAI endpoint change could break existing setups** → Mitigated: default is unchanged (`api.openai.com`). Only activates when `OPENAI_ENDPOINT` is explicitly set.
