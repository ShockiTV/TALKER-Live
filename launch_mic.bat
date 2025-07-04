@echo off
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
echo 4. Exit
echo.
echo ===============================================
echo.
echo   API Proxy by Mirrowel:
echo   https://github.com/Mirrowel/LLM-API-Key-Proxy
echo.
echo ===============================================
set /p choice="Enter your choice (1-4): "

if not '%choice%'=='' set choice=%choice:~0,1%

if '%choice%'=='1' goto gemini
if '%choice%'=='2' goto whisper_local
if '%choice%'=='3' goto whisper_api
if '%choice%'=='4' goto exit

echo Invalid choice. Please try again.
timeout /t 2 >nul
goto menu

:gemini
echo Launching with Gemini Proxy...
start "TALKER Mic - Gemini Proxy" talker_mic.exe gemini_proxy
goto end

:whisper_local
echo Launching with Whisper Local...
start "TALKER Mic - Whisper Local" talker_mic.exe whisper_local
goto end

:whisper_api
echo Launching with Whisper API...
start "TALKER Mic - Whisper API" talker_mic.exe whisper_api
goto end

:exit
exit

:end
echo.
echo The microphone application has been launched in a new window.
echo You can close this window now.
pause
