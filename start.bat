@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Preparing the game for the first launch...
    where py >nul 2>nul
    if not errorlevel 1 py -3.12 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" (
        where py >nul 2>nul
        if not errorlevel 1 py -3 -m venv .venv 2>nul
    )
    if not exist ".venv\Scripts\python.exe" (
        where python >nul 2>nul
        if not errorlevel 1 python -m venv .venv 2>nul
    )
    if not exist ".venv\Scripts\python.exe" (
        where python3 >nul 2>nul
        if not errorlevel 1 python3 -m venv .venv 2>nul
    )
    if not exist ".venv\Scripts\python.exe" (
        echo Python 3.10 or newer was not found.
        echo Install Python from https://www.python.org/downloads/ and run start.bat again.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import pygame" 2>nul
if errorlevel 1 (
    echo Installing Pygame...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Could not install the required packages. Check the internet connection.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 (
    echo.
    echo The game closed with an error.
    pause
)
