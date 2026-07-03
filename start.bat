@echo off
title BetterPortal
cd /d "%~dp0"

rem Eigenes venv bevorzugen, falls vorhanden
if exist "venv\scripts\python.exe" (
    set "PY=venv\scripts\python.exe"
) else (
    set "PY=python"
    where python >nul 2>&1 || (
        echo Python nicht gefunden! Bitte von python.org installieren.
        pause
        exit /b 1
    )
)

%PY% -c "import flask" 2>nul || %PY% -m pip install flask
%PY% -c "import keyboard" 2>nul || %PY% -m pip install keyboard
%PY% -c "import pywinauto" 2>nul || %PY% -m pip install pywinauto
%PY% main.py
pause
