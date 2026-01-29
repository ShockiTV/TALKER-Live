@echo off
REM Launch TALKER Python Service
REM This script starts the Python service that receives game events via ZeroMQ

echo ===================================
echo  T.A.L.K.E.R. Expanded - Python Service
echo ===================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Navigate to service directory
cd /d "%~dp0talker_service"

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install/update dependencies
echo Checking dependencies...
pip install -q -e . 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -e .
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Starting TALKER Python Service...
echo Press Ctrl+C to stop
echo.

REM Run the service
python run.py

pause
