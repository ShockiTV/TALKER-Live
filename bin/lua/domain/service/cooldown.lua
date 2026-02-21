-- domain/service/cooldown.lua
-- Generic CooldownManager that replaces the near-identical cooldown logic scattered
-- across 5+ trigger scripts (death, injury, artifact, anomalies, task).
--
-- Design decisions:
--   • Named timer slots — each slot tracks its own independent timers so a single
--     CooldownManager instance can serve multi-slot triggers (e.g. artifact: pickup/use/equip)
--   • Optional anti-spam layer — when anti_spam_ms is set, events closer together than
--     that threshold abort entirely (return nil) before any cooldown check
--   • Configurable on-cooldown behaviour:
--       "silent" (default)  → return true when cooldown is still active
--       "abort"             → return nil   when cooldown is still active
--
-- check() return convention (mirrors existing get_silence_status() convention):
--   nil   = abort    (anti-spam triggered, or mode == Off)
--   true  = silent   (cooldown active, or mode == Silent)
--   false = speak    (cooldown elapsed and mode == On)
local M = {}

--- Create a new CooldownManager instance.
-- @param config table:
--   cooldown_ms   (required) Dialogue cooldown duration in milliseconds
--   anti_spam_ms  (optional) Anti-spam window; events this close together are aborted
--   on_cooldown   (optional) "silent" (default) | "abort"
-- @return CooldownManager instance
function M.new(config)
    assert(config, "CooldownManager.new: config is required")
    assert(config.cooldown_ms, "CooldownManager.new: cooldown_ms is required")

    local cd = {
        cooldown_ms   = config.cooldown_ms,
        anti_spam_ms  = config.anti_spam_ms,          -- nil = no anti-spam layer
        on_cooldown   = config.on_cooldown or "silent",
        slots         = {},                            -- [slot_name] → { last_event=0, last_dialogue=0 }
    }

    --- Check whether an event on the given slot should speak, stay silent, or be aborted.
    -- @param slot         Named timer slot (string)
    -- @param current_time Current game time in milliseconds
    -- @param mode         MCM mode: 0=On, 1=Off, 2=Silent
    -- @return  false  → speak     (cooldown elapsed, mode On)
    --          true   → silent    (cooldown active, or mode Silent)
    --          nil    → abort     (anti-spam, or mode Off)
    function cd:check(slot, current_time, mode)
        -- Mode Off: always abort immediately
        if mode == 1 then return nil end

        -- Initialise slot state on first use
        if not self.slots[slot] then
            self.slots[slot] = { last_event = 0, last_dialogue = 0 }
        end
        local state = self.slots[slot]

        -- Anti-spam check (only when configured)
        if self.anti_spam_ms then
            if (current_time - state.last_event) < self.anti_spam_ms then
                return nil  -- Too soon — hard abort (not even a silent event)
            end
            state.last_event = current_time  -- Always update anti-spam timer when passing
        end

        -- Mode Silent: return true after anti-spam guard (if any)
        if mode == 2 then return true end

        -- Cooldown check (mode == 0: On)
        local elapsed = current_time - state.last_dialogue
        if elapsed < self.cooldown_ms then
            -- Cooldown active — honour on_cooldown config
            if self.on_cooldown == "abort" then return nil end
            return true  -- silent
        end

        -- Off cooldown: reset dialogue timer and request speech
        state.last_dialogue = current_time
        return false
    end

    return cd
end

return M
