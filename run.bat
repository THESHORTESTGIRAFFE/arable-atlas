@echo off
:: Set title of the Command Prompt window
title Arable Atlas - Production Server

echo ============================================================
echo   🌱  ARABLE ATLAS - EMMORPHIC PRODUCTION SERVER
echo ============================================================
echo.

:: 1. Check for Python installation and define PYTHON_CMD
set PYTHON_CMD=

:: Test if 'py' launcher works
py -3 --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3
    goto python_found
)

py --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto python_found
)

:: Test if 'python' works and is not the MS Store redirect stub
python --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto python_found
)

:: If we reach here, no valid Python installation was detected or it redirected to the MS Store
echo [ERROR] Python was not found or is pointing to the Windows App Store placeholder!
echo.
echo Please follow these steps to resolve this:
echo 1. Download and install Python from https://www.python.org/downloads/
echo 2. Check the box "Add Python to PATH" during installation.
echo 3. Disable the Windows App Execution Aliases:
echo    - Open the Windows Start Menu, search for "Manage app execution aliases".
echo    - Scroll down and turn OFF the toggles for "python.exe" and "python3.exe".
echo.
pause
exit /b 1

:python_found
echo [INFO] Using Python command: %PYTHON_CMD%
echo.

:: 2. Setup/Verify Virtual Environment
if not exist venv (
    echo [INFO] Virtual environment not found. Creating one...
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created successfully.
)

:: 3. Activate Virtual Environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)

:: 4. Auto-create .env file if it doesn't exist
if not exist .env (
    echo [INFO] .env file not found. Copying from .env.example...
    if exist .env.example (
        copy .env.example .env >nul
        echo [SUCCESS] Created .env file. Please update configurations if needed.
    ) else (
        echo [ERROR] .env.example file not found. Please create .env manually.
    )
)

:: 5. Install/Upgrade Dependencies
echo [INFO] Installing / updating required dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo [SUCCESS] All dependencies are ready.
echo.

:: 6. Launch Production Server
python run_production.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The server stopped unexpectedly or failed to start.
    pause
)

:: Deactivate venv on exit
call deactivate
