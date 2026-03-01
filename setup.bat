@echo off
REM ── TALKER Expanded – Developer Setup ──────────────────────────────
REM Run this once after cloning the repo.
REM
REM What it does:
REM   1. Marks the 200 TTS slot OGG files as skip-worktree so git
REM      ignores in-game modifications (TTS audio overwrites them
REM      during gameplay, but the committed silent placeholders
REM      should never be re-committed with real audio data).

echo.
echo === TALKER Expanded - Developer Setup ===
echo.
echo Marking 200 TTS slot files as skip-worktree...

for /L %%i in (1,1,200) do (
    git update-index --skip-worktree "gamedata/sounds/characters_voice/talker_tts/slot_%%i.ogg" 2>nul
)

echo.
echo Done. TTS slot files will no longer appear in git status after gameplay.
echo.
echo To undo (if you need to commit slot changes):
echo   git update-index --no-skip-worktree "gamedata/sounds/characters_voice/talker_tts/slot_*.ogg"
echo.
pause
