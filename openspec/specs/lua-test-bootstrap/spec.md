# lua-test-bootstrap

## Purpose

Defines the test bootstrap module that configures the mock engine and package paths for Lua unit tests.

## Requirements

### Requirement: Test bootstrap module exists

The system SHALL provide `tests/test_bootstrap.lua` that sets up all required engine mocks. Every Lua test file SHALL require this as its first line after package.path setup.

#### Scenario: Bootstrap sets up mock engine
- **WHEN** a test file calls `require("tests.test_bootstrap")`
- **THEN** `interface.engine` is replaced in `package.loaded` with `mock_engine`
- **AND** all engine globals are set to safe mocks (`talker_mcm`, `talker_game_queries`, `talker_game_commands`, `talker_game_async`, `talker_game_files`, `printf`, `ini_file`)

#### Scenario: Modules load after bootstrap
- **WHEN** `require("tests.test_bootstrap")` has been called
- **AND** a test requires any `bin/lua/` module (e.g., `require("framework.logger")`)
- **THEN** the module loads without error

#### Scenario: Bootstrap is idempotent
- **WHEN** `require("tests.test_bootstrap")` is called multiple times
- **THEN** only the first call performs setup (Lua's require caching)

### Requirement: Mock engine module exists

The system SHALL provide `tests/mocks/mock_engine.lua` that implements the full `interface/engine.lua` API with test-friendly stubs.

#### Scenario: Mock engine returns safe defaults
- **WHEN** `mock_engine.get_name(obj)` is called
- **THEN** it returns a string (e.g., `"Unknown"` or a name from the mock's internal data)

#### Scenario: Mock engine MCM returns defaults
- **WHEN** `mock_engine.get_mcm_value("witness_distance")` is called
- **THEN** it returns the default value from config_defaults (e.g., `25`)

#### Scenario: Mock engine command functions are no-ops
- **WHEN** `mock_engine.display_hud_message("test")` is called
- **THEN** it does nothing and does not error

#### Scenario: Mock engine query functions use mock data
- **WHEN** `mock_engine.get_player()` is called
- **THEN** it returns a mock player object with `id = 0`

### Requirement: Mock engine supports injectable test data

The mock engine SHALL allow tests to inject custom data for specific test scenarios.

#### Scenario: Override mock return value
- **WHEN** a test calls `mock_engine._set("get_location_name", "Rostok")` (or equivalent injection API)
- **AND** then calls `mock_engine.get_location_name()`
- **THEN** it returns `"Rostok"`

### Requirement: Previously passing tests continue to pass

All test files that currently pass SHALL continue to pass after the bootstrap migration.

#### Scenario: test_event.lua passes
- **WHEN** `lua5.1.exe tests/entities/test_event.lua` is run
- **THEN** all tests pass (exit code 0)

#### Scenario: test_filter_engine.lua passes
- **WHEN** `lua5.1.exe tests/infra/query/test_filter_engine.lua` is run
- **THEN** all tests pass (exit code 0)

#### Scenario: test_backstories.lua passes
- **WHEN** `lua5.1.exe tests/entities/test_backstories.lua` is run
- **THEN** all tests pass (exit code 0)

### Requirement: Previously failing tests are unblocked

Test files that previously failed due to missing engine globals SHALL pass after adopting the bootstrap.

#### Scenario: test_character.lua passes
- **WHEN** `lua5.1.exe tests/entities/test_character.lua` is run with bootstrap
- **THEN** all tests pass (Character.new() works with mock engine)

#### Scenario: test_talker.lua passes
- **WHEN** `lua5.1.exe tests/app/test_talker.lua` is run with bootstrap
- **THEN** all tests pass

#### Scenario: test_logger.lua passes
- **WHEN** `lua5.1.exe tests/utils/test_logger.lua` is run with bootstrap
- **THEN** all tests pass (log.error no longer crashes)

#### Scenario: test_file_io.lua passes
- **WHEN** `lua5.1.exe tests/utils/test_file_io.lua` is run with bootstrap
- **THEN** all tests pass
