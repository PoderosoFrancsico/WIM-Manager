@echo off
setlocal
cd /d "%~dp0"
if not exist ".build-env\Scripts\python.exe" (
    py -3 -m venv .build-env
    if errorlevel 1 goto error
)
".build-env\Scripts\python.exe" -m pip install PyInstaller
if errorlevel 1 goto error
".build-env\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --name WIMapp main.py
if errorlevel 1 goto error
echo Ejecutable creado en: %CD%\dist\WIMapp.exe
pause
exit /b 0
:error
echo No se pudo generar el ejecutable. Revisa el mensaje anterior.
pause
exit /b 1
