@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
    echo No se encontro el lanzador de Python. Instala Python 3 con Tcl/Tk y el lanzador py.
    pause
    exit /b 1
)
py -3 "%~dp0launcher.py"
if errorlevel 1 pause
