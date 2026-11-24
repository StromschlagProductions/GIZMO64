@echo off
cd /d "%~dp0"
python gizmo_bridge.py
if %errorlevel%==9009 py -3 gizmo_bridge.py
