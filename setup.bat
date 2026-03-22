@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   LINUP v12.0  -  Windows Setup
echo ============================================================
echo.

:: ============================================================
:: STEP 1 - Check / install Python
:: ============================================================
echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Downloading Python 3.12.10 installer...
    echo.
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%TEMP%\python_installer.exe'" 2>nul
    if errorlevel 1 (
        echo ERROR: Could not download Python. Check your internet connection.
        echo Download manually from: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo Installing Python silently (this may take a minute)...
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    if errorlevel 1 (
        echo ERROR: Python installation failed. Try running as Administrator.
        del "%TEMP%\python_installer.exe" >nul 2>&1
        pause
        exit /b 1
    )
    del "%TEMP%\python_installer.exe" >nul 2>&1

    :: Refresh PATH in this session so we don't need to reopen the window
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USERPATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYSPATH=%%B"
    set "PATH=!SYSPATH!;!USERPATH!"

    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo Python was installed but this window cannot see it yet.
        echo Please CLOSE this window and run setup.bat again.
        pause
        exit /b 0
    )
    echo OK - Python installed successfully.
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
    echo OK - Python !PYTHON_VERSION! found.
)
echo.

:: ============================================================
:: STEP 2 - Virtual environment
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
:: STEP 3 - Activate venv + upgrade pip
:: ============================================================
echo [3/6] Upgrading pip...
call venv\Scripts\activate.bat
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
    echo NOTE: Flutter not found - only needed to build a standalone .exe.
    echo       To install: https://docs.flutter.dev/get-started/install/windows
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
if not exist run.bat (
    (
        echo @echo off
        echo call "%~dp0venv\Scripts\activate.bat"
        echo flet run "%~dp0main.py"
        echo pause
    ) > run.bat
    echo Created run.bat
)
echo.

echo ============================================================
echo   LINUP v12.0 - Setup complete!
echo ============================================================
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo   Python : !PYTHON_VERSION!
echo   Flet   : !FLET_VERSION!
echo   Folder : %CD%
echo ============================================================
echo.
echo HOW TO LAUNCH LINUP:
echo   - Double-click  run.bat        (easiest)
echo   - Or open a terminal and type:
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
