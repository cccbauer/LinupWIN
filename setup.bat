@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   LINUP Windows - Setup ^& Build
echo ============================================================
echo.

:: 1. Verify Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Download it from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo OK - Python %PYTHON_VERSION% found
echo.

:: 2. Create virtual environment
echo [2/5] Creating virtual environment...
if exist venv (
    echo NOTE: venv already exists, using it
) else (
    python -m venv venv
    echo OK - Virtual environment created
)
echo.

:: 3. Install dependencies
echo [3/5] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
pip install "flet>=0.25.0"
if errorlevel 1 (
    echo ERROR: Failed to install flet.
    pause
    exit /b 1
)
echo OK - Flet installed
echo.

:: 4. Check Flutter (needed only to build .exe, not to run)
echo [4/5] Checking Flutter...
flutter --version >nul 2>&1
if errorlevel 1 (
    echo NOTE: Flutter not found - only needed to build .exe
    echo       Download: https://docs.flutter.dev/get-started/install/windows
    set FLUTTER_OK=0
) else (
    for /f "tokens=2" %%v in ('flutter --version 2^>^&1 ^| findstr /i "Flutter"') do set FLUTTER_VERSION=%%v
    echo OK - Flutter !FLUTTER_VERSION! found
    set FLUTTER_OK=1
)
echo.

:: 5. Summary
echo [5/5] Summary
echo ============================================================
echo Python:    %PYTHON_VERSION%
for /f "tokens=2" %%v in ('pip show flet 2^>^&1 ^| findstr Version') do echo Flet:      %%v
echo Project:   %CD%
echo ============================================================
echo.
echo Setup complete!
echo.
echo COMMANDS:
echo   Activate venv:    venv\Scripts\activate
echo   Run (window):     flet run main.py
echo   Build .exe:       flet build windows
echo.
echo The .exe will be in: build\windows\
echo.
pause
