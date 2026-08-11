@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --onefile --name PDFCropGUI --collect-all fitz --additional-hooks-dir=. main.py
if errorlevel 1 goto :error
echo.
echo Build complete: dist\PDFCropGUI.exe
pause
exit /b 0

:error
echo.
echo Build failed. Review the messages above.
pause
exit /b 1
