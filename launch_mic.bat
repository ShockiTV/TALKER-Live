@echo off
REM TALKER Microphone Launcher
REM Supports both pre-built exe (talker_mic.exe) and direct Python launch.

:menu
cls
echo ===============================================
echo  TALKER Microphone Launcher
echo ===============================================
echo.
echo Select a transcription provider:
echo.
echo 1. Gemini via API Proxy (Link below(Required))
echo 2. Whisper Local
echo 3. Whisper API (OpenAI)
echo.
echo 4. Launch via Python  (requires Python + pyzmq)
echo.
echo 5. Exit
echo.
echo ===============================================
echo.
echo   API Proxy by Mirrowel:
echo   https://github.com/Mirrowel/LLM-API-Key-Proxy
echo.
echo ===============================================
set /p choice="Enter your choice (1-5): "

if not '%choice%'=='' set choice=%choice:~0,1%

if '%choice%'=='1' goto gemini
if '%choice%'=='2' goto whisper_local
if '%choice%'=='3' goto whisper_api
if '%choice%'=='4' goto python_menu
if '%choice%'=='5' goto exit

echo Invalid choice. Please try again.
timeout /t 2 >nul
goto menu

:gemini
IF NOT EXIST talker_mic.exe goto no_exe
echo Launching with Gemini Proxy...
start "TALKER Mic - Gemini Proxy" talker_mic.exe gemini_proxy
goto end

:whisper_local
IF NOT EXIST talker_mic.exe goto no_exe
echo Launching with Whisper Local...
start "TALKER Mic - Whisper Local" talker_mic.exe whisper_local
goto end

:whisper_api
IF NOT EXIST talker_mic.exe goto no_exe
echo Launching with Whisper API...
start "TALKER Mic - Whisper API" talker_mic.exe whisper_api
goto end

:python_menu
cls
echo ===============================================
echo  Python Launch - Select provider:
echo ===============================================
echo.
echo 1. Gemini via API Proxy
echo 2. Whisper Local
echo 3. Whisper API (OpenAI)
echo 4. Whisper Local  with TTS
echo 5. Whisper API    with TTS
echo.
echo 6. Back
echo.
set /p pchoice="Enter your choice (1-6): "

if not '%pchoice%'=='' set pchoice=%pchoice:~0,1%

if '%pchoice%'=='1' goto py_gemini
if '%pchoice%'=='2' goto py_whisper_local
if '%pchoice%'=='3' goto py_whisper_api
if '%pchoice%'=='4' goto py_whisper_local_tts
if '%pchoice%'=='5' goto py_whisper_api_tts
if '%pchoice%'=='6' goto menu
goto python_menu

:py_setup
REM Create venv if it doesn't exist and install dependencies
set MIC_DIR=%~dp0talker_bridge\python
if not exist "%MIC_DIR%\.venv" (
    echo Creating virtual environment for talker_bridge...
    python -m venv "%MIC_DIR%\.venv"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        goto menu
    )
)
REM Install/update dependencies
echo Checking talker_bridge dependencies...
"%MIC_DIR%\.venv\Scripts\pip.exe" install -q -r "%MIC_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    goto menu
)
goto %py_target%

:py_gemini
set py_target=py_gemini_run
goto py_setup
:py_gemini_run
echo Launching Python mic with Gemini Proxy...
start "TALKER Mic (Python) - Gemini Proxy" /D "%~dp0talker_bridge\python" cmd /k ".venv\Scripts\python.exe main.py gemini_proxy"
goto end

:py_whisper_local
set py_target=py_whisper_local_run
goto py_setup
:py_whisper_local_run
echo Launching Python mic with Whisper Local...
start "TALKER Mic (Python) - Whisper Local" /D "%~dp0talker_bridge\python" cmd /k ".venv\Scripts\python.exe main.py whisper_local"
goto end

:py_whisper_api
set py_target=py_whisper_api_run
goto py_setup
:py_whisper_api_run
echo Launching Python mic with Whisper API...
start "TALKER Mic (Python) - Whisper API" /D "%~dp0talker_bridge\python" cmd /k ".venv\Scripts\python.exe main.py whisper_api"
goto end

:py_whisper_local_tts
set py_target=py_whisper_local_tts_run
goto py_setup
:py_whisper_local_tts_run
echo Launching Python mic with Whisper Local + TTS...
start "TALKER Mic (Python) - Whisper Local + TTS" /D "%~dp0talker_bridge\python" cmd /k ".venv\Scripts\python.exe main.py whisper_local --tts"
goto end

:py_whisper_api_tts
set py_target=py_whisper_api_tts_run
goto py_setup
:py_whisper_api_tts_run
echo Launching Python mic with Whisper API + TTS...
start "TALKER Mic (Python) - Whisper API + TTS" /D "%~dp0talker_bridge\python" cmd /k ".venv\Scripts\python.exe main.py whisper_api --tts"
goto end

:no_exe
echo.
echo talker_mic.exe not found.
echo Please download it from the latest release on GitHub:
echo https://github.com/Mirrowel/TALKER/releases
echo.
echo Alternatively, choose option 4 to launch via Python.
echo.
pause
goto menu

:exit
exit

:end
echo.
echo The microphone application has been launched in a new window.
echo You can close this window now.
pause
