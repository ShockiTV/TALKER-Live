## 1. Fix Broken Load Check References

- [x] 1.1 Remove `infra.STALKER.unique_backstories` from core_libs in `talker_game_load_check.script`
- [x] 1.2 Remove `infra.STALKER.unique_personalities` from core_libs in `talker_game_load_check.script`

## 2. Remove Unused Imports and Functions

- [x] 2.1 Remove `require("domain.model.item")` import from `bin/lua/domain/model/event.lua`
- [x] 2.2 Remove `get_player_weapon()` function from `bin/lua/infra/game_adapter.lua`
- [x] 2.3 Remove `create_item()` function from `bin/lua/infra/game_adapter.lua`
- [x] 2.4 Remove `Item` import from `bin/lua/infra/game_adapter.lua`

## 3. Delete Vestigial HTTP Modules

- [x] 3.1 Delete `bin/lua/infra/HTTP/HTTP.lua`
- [x] 3.2 Delete `bin/lua/infra/HTTP/pollnet.lua`

## 4. Clean Up Related Tests

- [x] 4.1 Delete `tests/live/real_http_requests/` directory

## 5. Verification

- [x] 5.1 Run relevant Lua tests to ensure no regressions
- [x] 5.2 Verify `talker_game_load_check.script` loads without errors
