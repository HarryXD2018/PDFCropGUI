@echo off
setlocal
cd /d "%~dp0"
set "DEPS_MARKER=.venv\.pdfcrop-gui-1.2.0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
if not exist "%DEPS_MARKER%" (
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto :error
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
  >"%DEPS_MARKER%" echo ready
)
".venv\Scripts\pythonw.exe" main.py
exit /b 0

:error
echo.
echo Initialization failed. Please check Python and network access.
pause
exit /b 1
