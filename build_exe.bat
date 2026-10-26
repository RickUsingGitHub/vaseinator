@echo off
rem Build the Windows app as one self-contained file: dist\Vaseinator.exe
cd /d "%~dp0"
tasklist /FI "IMAGENAME eq Vaseinator.exe" 2>nul | find /I "Vaseinator.exe" >nul
if not errorlevel 1 (
    echo Vaseinator is running - close it first, then build again.
    exit /b 1
)
if not exist .venv\Scripts\python.exe (
    python -m venv .venv || goto :error
)
.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller || goto :error
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile ^
    --name Vaseinator ^
    --icon assets\icon.ico ^
    --add-data "assets;assets" ^
    --exclude-module tkinter ^
    main.py || goto :error
echo.
if exist build rmdir /s /q build
echo Done: dist\Vaseinator.exe
exit /b 0
:error
echo Build failed.
exit /b 1
