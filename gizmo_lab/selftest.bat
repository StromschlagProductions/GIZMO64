@echo off
setlocal
cd /d "%~dp0"
python -c "import sys; sys.exit(sys.version_info[0] != 3)" >nul 2>&1
if not errorlevel 1 (
  python selftest.py
) else (
  py -3 selftest.py
)
set "GIZMO_SELFTEST_EXIT=%errorlevel%"
echo.
if "%GIZMO_SELFTEST_EXIT%"=="0" (echo [+] Selbsttest erfolgreich.) else (echo [!] Selbsttest fehlgeschlagen. Bericht und Fehler oben pruefen.)
pause
exit /b %GIZMO_SELFTEST_EXIT%
