@echo off
title SKSS-MIS Setup
cd /d "%~dp0"

echo Checking Python...
where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=py
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        echo.
        echo ERROR: Python is not installed or not in PATH.
        echo Download Python from https://www.python.org/downloads/
        echo During install, check "Add python.exe to PATH".
        echo.
        pause
        exit /b 1
    )
)

echo Using: %PYTHON%
%PYTHON% --version

if not exist .venv (
    echo Creating virtual environment...
    %PYTHON% -m venv .venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Creating staff user...
python seed_staff.py staff staff123

echo.
echo Setup complete! Double-click start.bat to run SKSS-MIS.
pause
