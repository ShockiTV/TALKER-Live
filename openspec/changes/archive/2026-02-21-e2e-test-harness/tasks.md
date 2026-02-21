## 1. Dependencies & Configuration

- [x] 1.1 Add `respx>=0.20.0`, `mcp>=1.0.0`, `pytest-json-report>=1.5.0` to `[project.optional-dependencies] dev` in `talker_service/pyproject.toml`
- [x] 1.2 Install updated dev dependencies into the venv: `pip install -e ".[dev]"`
- [x] 1.3 Create `.claude/settings.json` with `mcpServers.talker-tests` pointing to venv Python and `mcp_test_runner.py`
- [x] 1.4 Create `talker_service/tests/e2e/__init__.py` and `talker_service/tests/e2e/scenarios/` directory

## 2. ZMQRouter Context Parameter

- [x] 2.1 Add optional `context: zmq.asyncio.Context | None = None` parameter to `ZMQRouter.__init__` in `talker_service/src/talker_service/transport/router.py`
- [x] 2.2 Use provided context for socket creation when given, otherwise create own context as before
- [x] 2.3 In `ZMQRouter.shutdown()`, skip `context.term()` when context was provided externally (caller owns it)
- [x] 2.4 Update `test_router.py` to verify existing behavior is unchanged (no context arg still works)

## 3. LuaSimulator

- [x] 3.1 Create `talker_service/tests/e2e/lua_simulator.py` with `LuaSimulator` class
- [x] 3.2 Implement PUB socket binding on `inproc://lua-to-python` and SUB socket connecting to `inproc://python-to-lua`
- [x] 3.3 Implement `publish(topic, payload_dict)` method that sends `"{topic} {json}"` wire string
- [x] 3.4 Implement background `poll_loop()` async task that receives from SUB socket continuously
- [x] 3.5 Implement state query auto-response: parse `request_id` from received query, look up `state_mocks` by topic, publish `state.response` with `request_id` injected
- [x] 3.6 Record all received messages in `received_from_service: list[str]` and all sent in `published_to_service: list[str]`
- [x] 3.7 Set `done_event: asyncio.Event` when `dialogue.display` is received
- [x] 3.8 Implement `close()` to cancel poll task and close sockets (does not call `context.term()`)

## 4. E2eHarness and RunResult

- [x] 4.1 Create `talker_service/tests/e2e/harness.py` with `RunResult` dataclass (`state_queries`, `http_calls`, `zmq_published`)
- [x] 4.2 Implement `E2eHarness` class that creates one shared `zmq.asyncio.Context`
- [x] 4.3 Wire `ZMQRouter` with `sub_endpoint="inproc://lua-to-python"`, `pub_endpoint="inproc://python-to-lua"`, shared context
- [x] 4.4 Wire `LuaSimulator` with same shared context, binding before router connects
- [x] 4.5 Wire real `StateQueryClient` and real `DialogueGenerator` using the router
- [x] 4.6 Implement `run(scenario)`: configure respx mocks, publish input, await `done_event` (5s timeout), return `RunResult`
- [x] 4.7 Implement `_collect_run_result()`: strip `request_id` from state queries (Option A), collect HTTP call bodies from respx, collect `zmq_published` from `LuaSimulator.received_from_service`
- [x] 4.8 Implement `async_shutdown()`: cancel background tasks, call `router.shutdown()`, call `lua_sim.close()`, call `context.term()`
- [x] 4.9 Expose harness as a `pytest` async fixture in `talker_service/tests/e2e/conftest.py`

## 5. Scenario Files and Test Runner

- [x] 5.1 Create `talker_service/tests/e2e/scenario_loader.py` with `load_scenario(path)` and `discover_scenarios(dir)` functions
- [x] 5.2 Create `talker_service/tests/e2e/assertions.py` with `assert_scenario(result, scenario)` implementing deep `==` per declared `expected` key
- [x] 5.3 Create `talker_service/tests/e2e/test_scenarios.py` with `@pytest.mark.parametrize` over `discover_scenarios("scenarios/")`
- [x] 5.4 Add pytest hook in conftest to write `RunResult` to `.test_artifacts/last_run/payloads.json` after each test (keyed by node ID)
- [x] 5.5 Create `talker_service/tests/e2e/scenarios/death_wolf_full.json` — T1 scenario migrated from `test_event_lifecycle.py::test_T1_death_full_deadleader_narrative`; `input` uses `{ topic, payload }` structured objects (no raw wire strings anywhere in scenario files)

## 6. MCP Test Runner Server

- [x] 6.1 Create `talker_service/mcp_test_runner.py` using `mcp` SDK with server name `talker-tests`
- [x] 6.2 Implement `list_tests(path?)` tool: runs `pytest --collect-only -q --no-header`, parses node IDs, returns `{ tests, count }`
- [x] 6.3 Implement `run_tests(pattern?, path?, verbose?, fail_fast?)` tool: runs pytest with `--json-report`, returns `{ passed, failed, errors, duration_s, failures, returncode }`
- [x] 6.4 Implement `run_single_test(node_id)` tool: runs one test with `--tb=long -v`, returns structured result plus full `stdout`
- [x] 6.5 Implement `get_test_source(node_id)` tool: parses file and extracts the specific test function source using `ast`; for parametrized e2e tests also returns corresponding scenario file content under `scenario_file`
- [x] 6.6 Implement `get_last_run_results()` tool: reads cached results written by `run_tests` / `run_single_test` from `talker_service/.test_artifacts/last_run/results.json`
- [x] 6.7 Implement `get_captured_payloads(test_id?)` tool: reads `talker_service/.test_artifacts/last_run/payloads.json`, filters by `test_id` if provided
- [x] 6.8 Add `asyncio.run(main())` entry point and `stdio_server` transport
