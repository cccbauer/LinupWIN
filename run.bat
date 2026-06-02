@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   LINUP v18.1.3  -  Windows Run
echo ============================================================
echo.

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found.
    echo Please run setup.bat first to initialize the environment.
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the Flet application
echo Launching Linup...
flet run main.py

endlocal
