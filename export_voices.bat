@echo off
REM TALKER Voice Export
REM Bakes voice audio files in mic_python\voices\ into .safetensors kvcache files.
REM Supports .wav, .mp3, and .ogg files — both flat (voices\bandit_1.wav) and
REM subdirectory layouts (voices\bandit_1\...\sample.ogg → bandit_1.safetensors).
REM Run once when new voice files or subdirectories are added.
REM
REM Flags:
REM   --force    Re-export even if .safetensors already exists
REM   --denoise  Apply DeepFilterNet noise reduction (requires: pip install deepfilternet)

set MIC_DIR=%~dp0mic_python\python

REM Create venv if needed and install dependencies
if not exist "%MIC_DIR%\.venv" (
    echo Creating virtual environment for mic_python...
    python -m venv "%MIC_DIR%\.venv"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo Installing / updating mic_python dependencies (including pocket-tts)...
"%MIC_DIR%\.venv\Scripts\pip.exe" install -q --timeout 120 -r "%MIC_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM --- DeepFilterNet venv (separate to avoid numpy conflict with pocket-tts) ---
if not exist "%MIC_DIR%\.venv_df" (
    echo Creating DeepFilterNet virtual environment...
    python -m venv "%MIC_DIR%\.venv_df"
    if errorlevel 1 (
        echo ERROR: Failed to create DeepFilterNet venv
        pause
        exit /b 1
    )
)
echo Installing deepfilternet into dedicated venv...
"%MIC_DIR%\.venv_df\Scripts\pip.exe" install -q --timeout 300 "torch" "torchaudio<2.1" soundfile deepfilternet
if errorlevel 1 (
    echo WARNING: deepfilternet install failed - --denoise will not work
)

set DF_PYTHON=%MIC_DIR%\.venv_df\Scripts\python.exe

echo.
echo Exporting voice profiles...
"%MIC_DIR%\.venv\Scripts\python.exe" "%MIC_DIR%\export_voices.py" --df-python "%DF_PYTHON%" %*

echo.
pause
