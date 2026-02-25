@echo off
REM TALKER Bridge Launcher
REM Launches talker_bridge which proxies game traffic to/from talker_service
REM and handles audio capture + TTS playback.
REM
REM Supports both pre-built exe (talker_bridge.exe) and direct Python launch.

:menu
cls
echo ===============================================
echo  TALKER Bridge Launcher
echo ===============================================
echo.
echo 1. Launch (Executable)
echo 2. Launch via Python  (requires Python 3.10+)
echo.
echo 3. Exit
echo.
echo ===============================================
set /p choice="Enter your choice (1-3): "

if not '%choice%'=='' set choice=%choice:~0,1%

if '%choice%'=='1' goto exe_launch
if '%choice%'=='2' goto py_launch
if '%choice%'=='3' goto exit

echo Invalid choice. Please try again.
timeout /t 2 >nul
goto menu

:exe_launch
IF NOT EXIST talker_bridge.exe goto no_exe
echo Launching TALKER Bridge...
start "TALKER Bridge" talker_bridge.exe
goto end

:py_launch
REM Create venv if it doesn't exist and install dependencies
set BRIDGE_DIR=%~dp0talker_bridge\python
if not exist "%BRIDGE_DIR%\.venv" (
    echo Creating virtual environment for talker_bridge...
    python -m venv "%BRIDGE_DIR%\.venv"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        goto menu
    )
)
REM Install/update dependencies
echo Checking talker_bridge dependencies...
"%BRIDGE_DIR%\.venv\Scripts\pip.exe" install -q -r "%BRIDGE_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    goto menu
)
echo Launching TALKER Bridge via Python...
start "TALKER Bridge (Python)" /D "%~dp0talker_bridge\python" cmd /k ".venv\Scripts\python.exe main.py"
goto end

:no_exe
echo.
echo talker_bridge.exe not found.
echo Please download it from the latest release on GitHub:
echo https://github.com/Mirrowel/TALKER/releases
echo.
echo Alternatively, choose option 2 to launch via Python.
echo.
pause
goto menu

:exit
exit

:end
echo.
echo The TALKER Bridge has been launched in a new window.
echo You can close this window now.
pause
