@echo off
setlocal
cd /d "%~dp0"
python -c "import sys; sys.exit(sys.version_info[0] != 3)" >nul 2>&1
if not errorlevel 1 (
  python gizmo_lab.py %*
) else (
  py -3 gizmo_lab.py %*
)
if errorlevel 1 pause
