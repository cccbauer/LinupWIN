@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   LINUP v13.0  -  Windows Setup
echo ============================================================
echo.

:: ============================================================
:: STEP 1 - Check / install Python
:: ============================================================
echo [1/6] Checking Python...

:: Flag passed by the self-restart below so we never loop.
set POST_INSTALL=0
if "%~1"=="--post-install" set POST_INSTALL=1

set PYTHON_CMD=

:: ── If we already installed Python this session, jump straight to path lookup ──
if %POST_INSTALL%==1 goto :find_after_install

:: ── Normal check: prefer py launcher, then python ────────────────────────────
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set PYTHON_VERSION=%%v
    echo OK - Python !PYTHON_VERSION! found ^(py launcher^).
    goto :python_ok
)

python -c "import sys; sys.exit(0)" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
    echo OK - Python !PYTHON_VERSION! found.
    goto :python_ok
)

:: ── Python not found: download and install ───────────────────────────────────
echo Python not found. Downloading Python 3.12.10 installer...
echo.

powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%TEMP%\python_installer.exe' -UseBasicParsing" 2>nul
if errorlevel 1 (
    echo ERROR: Could not download Python installer.
    echo        Check your internet connection or download manually:
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing Python silently - this may take a minute...
echo ^(If prompted by Windows security, click Yes^)
echo.

start /wait "" "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
set INST_ERR=%errorlevel%
del "%TEMP%\python_installer.exe" >nul 2>&1

if %INST_ERR% neq 0 (
    echo ERROR: Python installation failed ^(error %INST_ERR%^).
    echo        Try right-clicking setup.bat and choosing "Run as administrator".
    pause
    exit /b 1
)
echo Python installed successfully.
echo.

:: ── After install: try the known per-user install path first ─────────────────
:: This avoids needing to wait for PATH to propagate to a new window.
:find_after_install
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) do (
    if exist %%P (
        set PYTHON_CMD=%%P
        for /f "tokens=2" %%v in ('%%P --version 2^>^&1') do set PYTHON_VERSION=%%v
        echo OK - Python !PYTHON_VERSION! at %%P
        goto :python_ok
    )
)

:: Couldn't find the exe at the expected path — do a one-time restart so a
:: fresh cmd window inherits the updated PATH from the registry.
if %POST_INSTALL%==0 (
    echo PATH not updated yet. Opening a fresh window to continue setup...
    start "" cmd /c ""%~f0" --post-install & pause"
    exit /b 0
)

:: Still not found after restart — give up.
echo ERROR: Python was installed but cannot be located.
echo        Please restart your computer and run setup.bat again.
pause
exit /b 1

:python_ok
echo.

:: ============================================================
:: STEP 2 - Virtual environment
:: ============================================================
echo [2/6] Setting up virtual environment...
if exist venv (
    echo NOTE: venv already exists, reusing it.
) else (
    !PYTHON_CMD! -m venv venv
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
    echo OK - Virtual environment created.
)
echo.

:: ============================================================
:: STEP 3 - Activate venv + upgrade pip
:: ============================================================
echo [3/6] Activating venv and upgrading pip...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate virtual environment.
    echo        Delete the "venv" folder and run setup.bat again.
    pause
    exit /b 1
)
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    pause
    exit /b 1
)
echo OK - pip up to date.
echo.

:: ============================================================
:: STEP 4 - Install Flet
:: ============================================================
echo [4/6] Installing Flet...
pip install "flet>=0.25.0" --quiet
if errorlevel 1 (
    echo ERROR: Failed to install Flet.
    echo        Check your internet connection and try again.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('pip show flet 2^>^&1 ^| findstr Version') do set FLET_VERSION=%%v
echo OK - Flet !FLET_VERSION! installed.
echo.

:: ============================================================
:: STEP 5 - Flutter (optional, only needed to build .exe)
:: ============================================================
echo [5/6] Checking Flutter (optional)...
flutter --version >nul 2>&1
if errorlevel 1 (
    echo NOTE: Flutter not found - only needed if you want to build a standalone .exe.
    echo       Install guide: https://docs.flutter.dev/get-started/install/windows
    set FLUTTER_OK=0
) else (
    for /f "tokens=2" %%v in ('flutter --version 2^>^&1 ^| findstr /i "Flutter"') do set FLUTTER_VERSION=%%v
    echo OK - Flutter !FLUTTER_VERSION! found.
    set FLUTTER_OK=1
)
echo.

:: ============================================================
:: STEP 6 - Create run.bat + summary
:: ============================================================
echo [6/6] Finishing up...
(
    echo @echo off
    echo call "%~dp0venv\Scripts\activate.bat"
    echo flet run "%~dp0main.py"
    echo pause
) > run.bat
echo Created / updated run.bat
echo.

echo ============================================================
echo   LINUP v13.0 - Setup complete!
echo ============================================================
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo   Python : !PYTHON_VERSION!
echo   Flet   : !FLET_VERSION!
echo   Folder : %CD%
echo ============================================================
echo.
echo HOW TO LAUNCH LINUP:
echo   - Double-click  run.bat        (easiest)
echo   - Or open a terminal here and type:
echo         venv\Scripts\activate
echo         flet run main.py
echo.
if "!FLUTTER_OK!"=="1" (
    echo TO BUILD A STANDALONE .EXE:
    echo         flet build windows
    echo   Output: build\windows\
    echo.
)
pause
