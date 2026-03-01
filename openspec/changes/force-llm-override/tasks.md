# Implementation Tasks: Force LLM Service Override

These tasks document the steps to implement the LLM provider override mechanic within `talker_service`.

- [ ] Modify `talker_service/src/talker_service/config.py`
  - [ ] Add `force_proxy_llm: bool = False` to `Settings`.
  - [ ] Add `proxy_model: str = ""` to `Settings`.
- [ ] Update `talker_service/src/talker_service/llm/proxy_client.py`
  - [ ] Update `__init__` signature to allow setting `model` explicitly.
  - [ ] Handle properly applying `proxy_model` if provided, otherwise default to ENV or "default".
- [ ] Update `talker_service/src/talker_service/llm/factory.py`
  - [ ] Update proxy parameters section to accept/pass down `model` from kwargs/settings.
- [ ] Rewrite `talker_service/src/talker_service/__main__.py` `get_current_llm_client()` function
  - [ ] Import `settings` from `.config` if not already imported in scope.
  - [ ] Add conditional `if settings.force_proxy_llm:` branch. 
  - [ ] Ensure that under proxy override, `model_method = 3` (proxy) and `model_name` grabs `settings.proxy_model`.
  - [ ] Test `.env` loading by manually passing custom key and model.
- [ ] (Optional) Add a basic unit test or integration scenario for `get_current_llm_client` override.
- [ ] Update `README.md` or `.env.example` (if one exists) to document `FORCE_PROXY_LLM` and `PROXY_MODEL`.