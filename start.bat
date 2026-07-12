@echo off
title SKSS-MIS Server
cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment not found. Running setup first...
    call setup.bat
)

call .venv\Scripts\activate.bat

echo.
echo Starting SKSS-MIS...
python run.py
pause
