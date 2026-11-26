@echo off
setlocal
if not exist "%~dp0..\GIZMO.cmd" (
    echo [!] Die lokale LAB-Installation fehlt. Bitte zuerst GIZMO installieren.
    exit /b 1
)
call "%~dp0..\GIZMO.cmd" %*
