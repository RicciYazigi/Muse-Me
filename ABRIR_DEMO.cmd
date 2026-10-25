@echo off
setlocal
cd /d "%~dp0"
set "MUSE_DEMO_PYTHON=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "MUSE_DEMO_PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist ".venv\Scripts\python.exe" set "MUSE_DEMO_PYTHON=%CD%\.venv\Scripts\python.exe"
"%MUSE_DEMO_PYTHON%" -B demo.py
if errorlevel 1 goto failed
"%MUSE_DEMO_PYTHON%" -B make_viewer.py
if errorlevel 1 goto failed
start "" "%CD%\viewer.html"
exit /b 0
:failed
echo La demo fallo. Revisa Python y las dependencias de README.md.
pause
exit /b 1
