@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   LINUP Windows - Full Setup (Fresh Install)
echo ============================================================
echo.

:: ============================================================
:: STEP 1 — Check if Python is installed, install if missing
:: ============================================================
echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Downloading installer...
    echo.
    :: Download Python 3.12 installer using PowerShell
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
    if errorlevel 1 (
        echo ERROR: Could not download Python. Check your internet connection.
        echo Download manually from: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo Installing Python (this may take a minute)...
    :: /quiet = silent, PrependPath=1 = add to PATH automatically
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    if errorlevel 1 (
        echo ERROR: Python installation failed.
        pause
        exit /b 1
    )
    del "%TEMP%\python_installer.exe"
    echo OK - Python installed.
    echo.
    echo IMPORTANT: Close and reopen this window, then run setup.bat again.
    pause
    exit /b 0
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
    echo OK - Python %PYTHON_VERSION% found.
)
echo.

:: ============================================================
:: STEP 2 — Create virtual environment
:: ============================================================
echo [2/6] Setting up virtual environment...
if exist venv (
    echo NOTE: venv already exists, reusing it.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
    echo OK - Virtual environment created.
)
echo.

:: ============================================================
:: STEP 3 — Upgrade pip
:: ============================================================
echo [3/6] Upgrading pip...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
echo OK - pip up to date.
echo.

:: ============================================================
:: STEP 4 — Install Flet
:: ============================================================
echo [4/6] Installing Flet...
pip install "flet>=0.25.0" --quiet
if errorlevel 1 (
    echo ERROR: Failed to install Flet.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('pip show flet 2^>^&1 ^| findstr Version') do set FLET_VERSION=%%v
echo OK - Flet %FLET_VERSION% installed.
echo.

:: ============================================================
:: STEP 5 — Check Flutter (needed only to build .exe)
:: ============================================================
echo [5/6] Checking Flutter...
flutter --version >nul 2>&1
if errorlevel 1 (
    echo NOTE: Flutter not found.
    echo       Flutter is only needed if you want to build a standalone .exe.
    echo       To install Flutter visit: https://docs.flutter.dev/get-started/install/windows
    echo       You can run Linup now without Flutter using: flet run main.py
    set FLUTTER_OK=0
) else (
    for /f "tokens=2" %%v in ('flutter --version 2^>^&1 ^| findstr /i "Flutter"') do set FLUTTER_VERSION=%%v
    echo OK - Flutter !FLUTTER_VERSION! found.
    set FLUTTER_OK=1
)
echo.

:: ============================================================
:: STEP 6 — Summary
:: ============================================================
echo [6/6] Setup complete!
echo ============================================================
echo   Python : %PYTHON_VERSION%
echo   Flet   : %FLET_VERSION%
echo   Folder : %CD%
echo ============================================================
echo.
echo HOW TO RUN LINUP:
echo.
echo   Option A — Run directly (no build needed):
echo     1. Double-click run.bat  (created below)
echo     2. Or open a terminal here and type:
echo            venv\Scripts\activate
echo            flet run main.py
echo.
if "!FLUTTER_OK!"=="1" (
    echo   Option B — Build standalone .exe:
    echo            flet build windows
    echo     The .exe will be in: build\windows\
    echo.
)

:: Create a convenience run.bat for the user
if not exist run.bat (
    echo @echo off > run.bat
    echo call venv\Scripts\activate.bat >> run.bat
    echo flet run main.py >> run.bat
    echo Created run.bat — double-click it to launch Linup.
    echo.
)

pause
