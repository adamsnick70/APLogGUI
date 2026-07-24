# Build the frozen Windows app (dist\AP Log Plotter\AP Log Plotter.exe).
#
# Run from anywhere:  powershell -File packaging\windows\build.ps1
# Requires: pip install -r requirements.txt (PyInstaller included).

$ErrorActionPreference = 'Stop'

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot     = Split-Path -Parent (Split-Path -Parent $PackagingDir)

Write-Host "== Compiling .ui files ==" -ForegroundColor Cyan
python (Join-Path $RepoRoot 'tools\build_ui.py') --force

Write-Host "== Running PyInstaller ==" -ForegroundColor Cyan
pyinstaller (Join-Path $PackagingDir 'ap_log_plotter.spec') `
    --distpath (Join-Path $PackagingDir 'dist') `
    --workpath (Join-Path $PackagingDir 'build') `
    --noconfirm

Write-Host ""
Write-Host "Done: $(Join-Path $PackagingDir 'dist\AP Log Plotter\AP Log Plotter.exe')" -ForegroundColor Green
