@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please create .venv and install requirements.txt first. See README.md.
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\stop_previous.ps1"
if errorlevel 1 (
    echo Could not stop the previous Vynn instance.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
if errorlevel 1 pause
