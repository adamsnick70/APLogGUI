@echo off
rem Double-click this file to install AP Log Plotter on Windows 11.
rem It delegates to install_windows.ps1 (PowerShell), bypassing execution
rem policy just for this one script run.

set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install_windows.ps1"

echo.
pause
