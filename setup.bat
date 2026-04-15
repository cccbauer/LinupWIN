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

:: Prefer the Windows Python Launcher (py.exe) - it is always real Python.
:: Fall back to 'python', but verify it is not the Windows Store stub
:: (the stub exits 0 on some systems but cannot actually run scripts).
set PYTHON_CMD=

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

:: ── Python not found: download and install ────────────────────────────────
echo Python not found. Downloading Python 3.12.10 installer...
echo.

:: -UseBasicParsing avoids the IE engine requirement on fresh Windows installs
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

:: 'start /wait' blocks until the installer exits, which is more reliable
:: than running the .exe directly in some UAC configurations.
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
echo Restarting setup so the new PATH is picked up...
echo.

:: Open a fresh cmd window which will inherit the updated PATH from the registry.
:: The original window closes after launching the new one.
start "" cmd /k ""%~f0""
exit /b 0

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
