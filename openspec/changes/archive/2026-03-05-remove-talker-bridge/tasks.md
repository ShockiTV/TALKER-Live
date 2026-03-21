## 1. Delete Bridge Artifacts

- [x] 1.1 Delete `talker_bridge/` directory tree
- [x] 1.2 Delete `launch_talker_bridge.bat`
- [x] 1.3 Delete `test_bridge_config_issue.py` (root-level test)

## 2. MCM and Config Rename

- [x] 2.1 Rename `mic_ws_port` → `service_ws_port` (default 5558 → 5557) in `talker_mcm.script`
- [x] 2.2 Update `bin/lua/interface/config.lua` getter from `mic_ws_port` to `service_ws_port`
- [x] 2.3 Update `bin/lua/interface/config_defaults.lua` key and default value

## 3. Direct Service Connection (Lua Side)

- [x] 3.1 Rename `get_bridge_url()` → `get_service_url()` in `talker_ws_integration.script`; change default port to 5557
- [x] 3.2 Rename `get_bridge_channel()` → `get_service_channel()` across `talker_ws_*.script` files
- [x] 3.3 Update all callers of `get_bridge_channel()` in `talker_ws_query_handlers.script` and `talker_ws_command_handlers.script`
- [x] 3.4 Update `talker_input_chatbox.script` and `talker_input_microphone.script` if they reference bridge

## 4. Delete Bridge-Specific Tests

- [x] 4.1 Delete `tests/integration/test_bridge_config_sync.py` (Python)
- [x] 4.2 Delete `talker_service/tests/test_bridge_config.py` (Python)
- [x] 4.3 Delete `talker_service/tests/test_bridge_lua_closure.py` (Python)
- [x] 4.4 Remove or update any Lua test files that reference `bridge` (check `tests/infra/`)

## 5. Update E2E Tests

- [x] 5.1 Change direction assertions from `lua→bridge→service` to `lua→service` in `talker_service/tests/e2e/test_ws_api_contract.py`
- [x] 5.2 Change direction assertions from `service→bridge→lua` to `service→lua` in E2E tests

## 6. Update Documentation

- [x] 6.1 Update `AGENTS.md`: remove bridge from architecture diagram, communication flow, launch commands, and file references
- [x] 6.2 Update `README.md`: remove bridge launch instructions and references
- [x] 6.3 Update `docs/ws-api.yaml`: remove bridge from flow descriptions
- [x] 6.4 Update `docs/Python_Service_Setup.md`: remove bridge setup steps
- [x] 6.5 Update `.github/copilot-instructions.md`: remove bridge references

## 7. Verify and Run Tests

- [x] 7.1 Run Lua tests to verify no broken `require("infra.bridge.channel")` or bridge references
- [x] 7.2 Run Python tests to verify no import errors from deleted bridge test files
- [x] 7.3 Run E2E tests to verify updated direction assertions pass
