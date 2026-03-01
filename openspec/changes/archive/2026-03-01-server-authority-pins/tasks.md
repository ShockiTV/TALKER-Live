## 1. ConfigMirror Pin Mechanism

- [x] 1.1 Add `_pins: dict[str, Any]` storage and `pin(field, value)` method to `ConfigMirror`
- [x] 1.2 Update `ConfigMirror.get()` to check `_pins` before `_config`
- [x] 1.3 Add audit logging in `update()` / `sync()` when MCM value differs from pin
- [x] 1.4 Update `dump()` to include `pins` key in output
- [x] 1.5 Update cache-clearing logic in `update()` / `sync()` to compare effective (post-pin) values

## 2. Settings Model — New .env Keys

- [x] 2.1 Add `llm_provider`, `llm_model`, `llm_model_fast`, `stt_method` fields to `Settings` (all `Optional[str]`, default `None`)
- [x] 2.2 Add `openai_endpoint` field to `Settings` (default empty string)
- [x] 2.3 Implement backward-compat resolution: `FORCE_PROXY_LLM=true` → `llm_provider="proxy"`, `FORCE_LOCAL_WHISPER=true` → `stt_method="local"` (only when new keys absent)

## 3. Startup Pin Wiring

- [x] 3.1 In `__main__.py` lifespan, read `settings.llm_provider` / `llm_model` / `llm_model_fast` / `stt_method` and call `config_mirror.pin()` for each set value
- [x] 3.2 Remove `if force_proxy_llm` branching from `get_current_llm_client()` closure — just use `config_mirror.get()`
- [x] 3.3 Remove `if force_local_whisper` branching from `_init_stt_on_config()` — just use `config_mirror.get()`
- [x] 3.4 Log summary of active pins at startup

## 4. OpenAI Client Endpoint Override

- [x] 4.1 Change `OpenAIClient.API_URL` from class constant to instance `self.api_url`, initialized from `endpoint` param → `OPENAI_ENDPOINT` env → default
- [x] 4.2 Update `complete()` to use `self.api_url` instead of `self.API_URL`

## 5. .env Files

- [x] 5.1 Update `.env.example` with new keys (commented out, with documentation)
- [x] 5.2 Update `.env` with new keys (commented out)

## 6. Debug Endpoint

- [x] 6.1 Update `/debug/config` to include pins and effective values in response

## 7. Tests

- [x] 7.1 Unit tests for `ConfigMirror.pin()` — pin overrides get, unpinned passthrough, audit logging
- [x] 7.2 Unit tests for cache-clearing logic — skipped when pinned fields unchanged, triggered when effective values change
- [x] 7.3 Unit test for `Settings` backward-compat aliases
- [x] 7.4 Unit test for `OpenAIClient` endpoint override
