# map-transition-save (delta)

## Changes

### MODIFIED: Map transition save persists visit counts
Persistence moves from `talker_trigger_map_transition.script` local `save_state`/`load_state` to the `levels` domain repo via the persistence hub. Visit counts are still persisted, but through the domain layer.

### ADDED: Trigger script delegates persistence
The map transition trigger script SHALL NOT have its own `save_state`/`load_state` callbacks. All persistence SHALL be handled by the `levels` domain repo through `talker_game_persistence.script`.
