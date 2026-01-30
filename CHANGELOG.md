# Changelog

All notable changes to TALKER Expanded will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-01-30

### ⚠️ BREAKING CHANGES

- **Python service is now REQUIRED** for AI dialogue generation. The legacy Lua AI mode has been completely removed.
  - You MUST run `launch_talker_service.bat` before starting the game
  - There is no longer a fallback to Lua-based LLM calls
  - MCM toggles for "Enable Python AI" and "Enable ZMQ" have been removed

### Added

- **Service status notifications**: HUD messages now inform you when:
  - Python service is disconnected (after 15 seconds without response)
  - Python service reconnects after being disconnected
  - You attempt to trigger dialogue while service is offline
- **Heartbeat acknowledgement system**: Python service now acknowledges heartbeats from Lua, enabling reliable connection recovery after game pause/menu
- **LOG_HEARTBEAT configuration**: Set `LOG_HEARTBEAT=true` in `.env` to enable heartbeat logging for debugging

### Removed

- `bin/lua/infra/AI/` directory and all legacy AI modules (GPT.lua, OpenRouterAI.lua, local_ollama.lua, proxy.lua, etc.)
- `python_ai_enabled()` and `zmq_enabled()` config getters
- MCM toggles for Python AI and ZMQ (now always enabled)
- Legacy Lua AI code paths in `talker.lua`

### Changed

- ZMQ bridge now initializes unconditionally on mod load
- Connection timeout reduced from 30s to 15s for faster disconnect detection
- Updated documentation to reflect Python service is mandatory

## [0.2.0] - 2026-01-29

### Added

- Python service for AI dialogue generation (Phase 2)
- ZeroMQ bidirectional communication between Lua and Python
- Dialogue generator with speaker selection
- Memory compression handled by Python service
- State query system for fetching game data from Lua

## [0.1.0] - Initial Release

### Added

- Initial TALKER Expanded features
- MCM configuration support
- Three-tier memory system
- Whispering to companions
- Silent events mode
- Expanded backstories and personalities
