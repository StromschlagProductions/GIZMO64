@echo off
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" gizmo_lab\qa_local.py --real-gemma
) else (
  py -3 gizmo_lab\qa_local.py --real-gemma
)
if errorlevel 1 pause
