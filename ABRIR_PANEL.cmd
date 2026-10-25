@echo off
setlocal
cd /d "%~dp0"
set "MUSE_PYTHON=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "MUSE_PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist ".venv\Scripts\python.exe" set "MUSE_PYTHON=%CD%\.venv\Scripts\python.exe"
"%MUSE_PYTHON%" -B run_panel.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo No se pudo iniciar el panel. Revisa la instalacion de Python.
pause
exit /b 1
