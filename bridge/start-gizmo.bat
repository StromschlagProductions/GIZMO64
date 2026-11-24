@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto start_error

python -c "import sys; sys.exit(sys.version_info[0] != 3)" >nul 2>&1
if not errorlevel 1 (
    python "%~dp0gizmo_bridge.py"
) else (
    py -3 -c "import sys; sys.exit(sys.version_info[0] != 3)" >nul 2>&1
    if errorlevel 1 goto python_missing
    py -3 "%~dp0gizmo_bridge.py"
)

set "GIZMO_EXIT=%errorlevel%"
if not "%GIZMO_EXIT%"=="0" (
    echo.
    echo [!] GIZMO wurde mit Fehlercode %GIZMO_EXIT% beendet.
    echo [!] Die Fehlermeldung steht weiter oben in diesem Fenster.
    pause
)
exit /b %GIZMO_EXIT%

:python_missing
echo [!] Python 3 wurde weder als python noch als py -3 gefunden.
goto start_error

:start_error
echo [!] GIZMO konnte nicht gestartet werden.
pause
exit /b 1
