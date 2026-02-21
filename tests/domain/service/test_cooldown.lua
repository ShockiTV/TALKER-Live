package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit  = require('tests.utils.luaunit')
local Cooldown = require('domain.service.cooldown')

-- ──────────────────────────────────────────────────────────────────────────────
-- Construction
-- ──────────────────────────────────────────────────────────────────────────────

function testModuleLoads()
    luaunit.assertNotNil(Cooldown)
    luaunit.assertEquals(type(Cooldown.new), "function")
end

function testCreateSimpleCooldown()
    local cd = Cooldown.new({ cooldown_ms = 90000 })
    luaunit.assertNotNil(cd)
    luaunit.assertNil(cd.anti_spam_ms)
end

function testCreateWithAntiSpam()
    local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
    luaunit.assertNotNil(cd)
    luaunit.assertEquals(cd.anti_spam_ms, 5000)
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Mode handling
-- ──────────────────────────────────────────────────────────────────────────────

function testModeOff_returnsNil()
    local cd = Cooldown.new({ cooldown_ms = 5000 })
    local result = cd:check("default", 1000, 1)  -- mode 1 = Off
    luaunit.assertNil(result)
end

function testModeSilent_returnsTrue()
    local cd = Cooldown.new({ cooldown_ms = 5000 })
    local result = cd:check("default", 1000, 2)  -- mode 2 = Silent
    luaunit.assertTrue(result)
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Basic cooldown behaviour (no anti-spam)
-- ──────────────────────────────────────────────────────────────────────────────

function testCooldownNotElapsed_returnsTrue()
    local cd = Cooldown.new({ cooldown_ms = 90000 })
    -- First call at t=1000 speaks (returns false) and resets timer
    cd:check("default", 1000, 0)
    -- Only 49s elapsed — still on cooldown
    local result = cd:check("default", 50000, 0)
    luaunit.assertTrue(result)
end

function testCooldownElapsed_returnsFalse()
    local cd = Cooldown.new({ cooldown_ms = 90000 })
    cd:check("default", 1000, 0)   -- speak, reset timer
    local result = cd:check("default", 100000, 0)  -- 99s elapsed
    luaunit.assertFalse(result)
end

function testTimerResetOnSpeak()
    local cd = Cooldown.new({ cooldown_ms = 90000 })
    luaunit.assertFalse(cd:check("default", 100000, 0))  -- speak
    -- Immediately after — cooldown just reset
    luaunit.assertTrue(cd:check("default", 100001, 0))
end

function testFirstCheckWithNoHistory_speaks()
    -- No prior event means last_dialogue == 0, elapsed is huge → speak
    local cd = Cooldown.new({ cooldown_ms = 5000 })
    luaunit.assertFalse(cd:check("default", 9999999, 0))
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Named slots are independent
-- ──────────────────────────────────────────────────────────────────────────────

function testTwoIndependentSlots()
    local cd = Cooldown.new({ cooldown_ms = 5000 })
    -- Both slots speak on first trigger (no history)
    cd:check("player", 1000, 0)   -- player speaks at t=1000
    cd:check("npc",    2000, 0)   -- npc speaks at t=2000

    -- t=4000: player CD=3s elapsed (< 5s) → silent; npc CD=2s elapsed (< 5s) → silent
    luaunit.assertTrue(cd:check("player", 4000, 0))
    luaunit.assertTrue(cd:check("npc",    4000, 0))
end

function testNpcSlotIndependent_elapses()
    local cd = Cooldown.new({ cooldown_ms = 5000 })
    cd:check("player", 1000, 0)
    cd:check("npc",    2000, 0)
    -- t=8000: npc CD=6s elapsed (>5s) → speak again
    luaunit.assertFalse(cd:check("npc", 8000, 0))
    -- still on player CD (7s since t=1000 > 5s → actually elapsed too)
    luaunit.assertFalse(cd:check("player", 8000, 0))
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Anti-spam layer
-- ──────────────────────────────────────────────────────────────────────────────

function testAntiSpam_blocks()
    local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
    cd:check("pickup", 1000, 0)  -- first event, passes anti-spam (0 elapsed)
    -- 2s later — anti-spam blocks
    local result = cd:check("pickup", 3000, 0)
    luaunit.assertNil(result)
end

function testAntiSpam_passesButCooldownBlocks()
    local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
    cd:check("pickup", 1000, 0)  -- first event
    -- 9s later — anti-spam passes (9 > 5), cooldown blocks (9 < 60)
    local result = cd:check("pickup", 10000, 0)
    luaunit.assertTrue(result)
end

function testAntiSpam_bothPass()
    local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
    cd:check("pickup", 1000, 0)
    -- 69s later — both pass
    local result = cd:check("pickup", 70000, 0)
    luaunit.assertFalse(result)
end

function testAntiSpam_modeSilentAfterAntiSpam()
    local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
    cd:check("pickup", 1000, 0)
    -- Mode 2 (Silent), anti-spam passes (10s > 5s) → true
    local result = cd:check("pickup", 11000, 2)
    luaunit.assertTrue(result)
end

function testAntiSpam_modeSilentBlockedByAntiSpam()
    local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
    cd:check("pickup", 1000, 0)
    -- Mode 2 but anti-spam not cleared yet (2s < 5s) → nil
    local result = cd:check("pickup", 3000, 2)
    luaunit.assertNil(result)
end

-- ──────────────────────────────────────────────────────────────────────────────
-- on_cooldown behaviour
-- ──────────────────────────────────────────────────────────────────────────────

function testOnCooldown_defaultIsSilent()
    local cd = Cooldown.new({ cooldown_ms = 90000 })  -- default "silent"
    cd:check("default", 1000, 0)  -- speak
    luaunit.assertTrue(cd:check("default", 5000, 0))   -- on cooldown → silent (true)
end

function testOnCooldown_abortDropsEvent()
    local cd = Cooldown.new({ cooldown_ms = 90000, on_cooldown = "abort" })
    cd:check("default", 1000, 0)  -- speak
    local result = cd:check("default", 5000, 0)  -- on cooldown → nil (abort)
    luaunit.assertNil(result)
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Real-game timestamps: initial last_dialogue=0 means first event at T>>cooldown speaks.
-- BASE_TIME is large enough that (BASE_TIME - 0) > any cooldown used below.
-- ──────────────────────────────────────────────────────────────────────────────
local BASE = 2000000  -- 2000 seconds; safely above all cooldown_ms values used

-- ──────────────────────────────────────────────────────────────────────────────
-- Death trigger pattern: two slots, no anti-spam, on_cooldown="silent"
-- ──────────────────────────────────────────────────────────────────────────────

function testDeathTriggerPattern()
    local cd = Cooldown.new({ cooldown_ms = 90000 })
    -- player kills at BASE — elapsed from 0 is >> 90s → speak
    luaunit.assertFalse(cd:check("player", BASE, 0))
    -- 1s later — still on cooldown → silent
    luaunit.assertTrue(cd:check("player", BASE + 1000, 0))
    -- npc slot has no history → BASE - 0 >> 90s → speaks independently
    luaunit.assertFalse(cd:check("npc", BASE, 0))
    -- Silent mode always returns true regardless of timing
    luaunit.assertTrue(cd:check("player", BASE + 300000, 2))
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Injury trigger pattern: single slot, no anti-spam, on_cooldown="abort"
-- ──────────────────────────────────────────────────────────────────────────────

function testInjuryTriggerPattern()
    local cd = Cooldown.new({ cooldown_ms = 20000, on_cooldown = "abort" })
    luaunit.assertFalse(cd:check("default", BASE, 0))            -- speak (first time)
    luaunit.assertNil(cd:check("default",  BASE + 5000,  0))     -- on cooldown → abort
    luaunit.assertFalse(cd:check("default", BASE + 25000, 0))    -- elapsed → speak again
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Artifact trigger pattern: multi-slot, with anti-spam, on_cooldown="silent"
-- ──────────────────────────────────────────────────────────────────────────────

function testArtifactTriggerPattern()
    local cd = Cooldown.new({ cooldown_ms = 60000, anti_spam_ms = 5000 })
    -- pickup slot: first event at BASE (elapsed from 0 >> both thresholds)
    luaunit.assertFalse(cd:check("pickup", BASE, 0))             -- speak
    luaunit.assertNil(cd:check("pickup",  BASE + 2000, 0))       -- anti-spam → abort
    luaunit.assertTrue(cd:check("pickup", BASE + 10000, 0))      -- anti-spam ok, CD not done → silent
    luaunit.assertFalse(cd:check("pickup", BASE + 80000, 0))     -- both passed → speak
    -- use slot is independent — first call at BASE >> all thresholds → speaks
    luaunit.assertFalse(cd:check("use", BASE, 0))
end

os.exit(luaunit.LuaUnit.run())
