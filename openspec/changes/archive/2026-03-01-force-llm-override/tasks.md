# Implementation Tasks: Force LLM Service Override

These tasks document the steps to implement the LLM provider override mechanic within `talker_service`.

- [x] Modify `talker_service/src/talker_service/config.py`
  - [x] Add `force_proxy_llm: bool = False` to `Settings`.
  - [x] Add `proxy_model: str = ""` to `Settings`.
- [x] Update `talker_service/src/talker_service/llm/proxy_client.py`
  - [x] Update `__init__` signature to allow setting `model` explicitly.
  - [x] Handle properly applying `proxy_model` if provided, otherwise default to ENV or "default".
- [x] Update `talker_service/src/talker_service/llm/factory.py`
  - [x] Update proxy parameters section to accept/pass down `model` from kwargs/settings.
- [x] Rewrite `talker_service/src/talker_service/__main__.py` `get_current_llm_client()` function
  - [x] Import `settings` from `.config` if not already imported in scope.
  - [x] Add conditional `if settings.force_proxy_llm:` branch. 
  - [x] Ensure that under proxy override, `model_method = 3` (proxy) and `model_name` grabs `settings.proxy_model`.
  - [x] Test `.env` loading by manually passing custom key and model.
- [x] (Optional) Add a basic unit test or integration scenario for `get_current_llm_client` override.
- [x] Update `README.md` or `.env.example` (if one exists) to document `FORCE_PROXY_LLM` and `PROXY_MODEL`.