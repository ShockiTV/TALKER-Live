## Approach

Dead code removal and one-line bug fix. No architectural changes.

## Design Details

### Remove `commented_already`

Delete the variable declaration, its save line, and its load line. It is never read by any code path.

### Fix save bug

Line 98 currently reads:
```lua
m_data.level_visit_count = commented_already
```
This should be removed entirely (it was the bugged save for `commented_already`). The correct save of `level_visit_count` is already on line 97.

### Resulting save/load

After cleanup:
```lua
function save_state(m_data)
    m_data.level_visit_count = level_visit_count or {}
    m_data.previous_map = level.name()
end

function load_state(m_data)
    level_visit_count = m_data.level_visit_count or {}
    previous_map = m_data.previous_map
end
```

## Risks

None. The removed code was never active. The fix restores intended behavior for `level_visit_count` persistence.
