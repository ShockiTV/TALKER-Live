# framework-utils

## Purpose

Generic Lua utility functions with zero dependencies, extracted from `gamedata/scripts/` into `bin/lua/framework/utils.lua`. Used across the codebase by all layers.

## Requirements

### Requirement: Utils module exists at framework/utils.lua

The system SHALL provide a `framework/utils.lua` module containing common utility functions extracted from `gamedata/scripts/`. The module SHALL have zero dependencies on engine globals, domain modules, or infrastructure.

#### Scenario: Module loads without engine
- **WHEN** `require("framework.utils")` is called outside the STALKER engine
- **THEN** the module loads successfully and returns a table of utility functions

### Requirement: must_exist nil-guard function

The module SHALL provide `utils.must_exist(obj, func_name)` that raises an error if `obj` is nil.

#### Scenario: Non-nil value passes
- **WHEN** `utils.must_exist(some_table, "my_func")` is called with a non-nil value
- **THEN** no error is raised

#### Scenario: Nil value raises error
- **WHEN** `utils.must_exist(nil, "my_func")` is called
- **THEN** an error is raised with message containing `"my_func"` and `"nil"`

### Requirement: try protected-call wrapper

The module SHALL provide `utils.try(func, ...)` that wraps a function call in `pcall`, returning `nil` on error.

#### Scenario: Successful call returns result
- **WHEN** `utils.try(function() return 42 end)` is called
- **THEN** it returns `42`

#### Scenario: Failing call returns nil
- **WHEN** `utils.try(function() error("boom") end)` is called
- **THEN** it returns `nil` without propagating the error

### Requirement: join_tables array concatenation

The module SHALL provide `utils.join_tables(t1, t2)` that returns a new array containing all elements from both input arrays in order.

#### Scenario: Two arrays joined
- **WHEN** `utils.join_tables({1,2}, {3,4})` is called
- **THEN** it returns `{1, 2, 3, 4}`

#### Scenario: Nil-safe with first nil
- **WHEN** `utils.join_tables(nil, {3,4})` is called
- **THEN** it returns `{3, 4}`

#### Scenario: Nil-safe with second nil
- **WHEN** `utils.join_tables({1,2}, nil)` is called
- **THEN** it returns `{1, 2}`

### Requirement: Set conversion function

The module SHALL provide `utils.Set(t)` that converts an array to a set table (value→true mapping).

#### Scenario: Array to set conversion
- **WHEN** `utils.Set({"a", "b", "c"})` is called
- **THEN** it returns `{a = true, b = true, c = true}`

#### Scenario: Membership check
- **WHEN** a set is created from `{"alpha", "beta"}`
- **AND** `set["alpha"]` is checked
- **THEN** it returns `true`
- **AND** `set["gamma"]` returns `nil`

### Requirement: shuffle function

The module SHALL provide `utils.shuffle(tbl)` that performs an in-place Fisher-Yates shuffle of an array.

#### Scenario: Shuffle preserves elements
- **WHEN** `utils.shuffle({1,2,3,4,5})` is called
- **THEN** the returned table contains exactly the elements `{1,2,3,4,5}` (in any order)

#### Scenario: Shuffle modifies in place
- **WHEN** a table `t = {1,2,3}` is passed to `utils.shuffle(t)`
- **THEN** the original table `t` is modified (same reference)

### Requirement: safely error-wrapper function

The module SHALL provide `utils.safely(func, name)` that returns a new function wrapping `func` in `pcall`. On error, it SHALL log the error (if a logger is available) and return the error result.

#### Scenario: Wrapped function succeeds
- **WHEN** `local safe_fn = utils.safely(function() return 42 end, "test")`
- **AND** `safe_fn()` is called
- **THEN** it returns `42`

#### Scenario: Wrapped function fails
- **WHEN** `local safe_fn = utils.safely(function() error("boom") end, "test")`
- **AND** `safe_fn()` is called
- **THEN** it does not propagate the error
- **AND** the error is logged

### Requirement: array_iter iterator function

The module SHALL provide `utils.array_iter(arr)` that returns a stateful iterator over an array.

#### Scenario: Iterate over array
- **WHEN** `local next_val = utils.array_iter({10, 20, 30})`
- **AND** `next_val()` is called 3 times
- **THEN** it returns `10`, `20`, `30` in sequence
