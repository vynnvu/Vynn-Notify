@echo off
cd /d "%~dp0"
set "PET_PYTHON=.venv\Scripts\python.exe"
if not exist "%PET_PYTHON%" (py -3.11 -m venv .venv)
"%PET_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (echo Install failed & pause & exit /b 1)
"%PET_PYTHON%" tools\generate_icon.py
if errorlevel 1 (echo Icon generation failed & pause & exit /b 1)
"%PET_PYTHON%" -m PyInstaller --noconfirm --clean Vynn_Notify.spec
if errorlevel 1 (echo Build failed & pause & exit /b 1)
echo Built at dist\Vynn_Notify.exe
pause
