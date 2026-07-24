# Build the frozen Windows app (dist\AP Log Plotter\AP Log Plotter.exe).
#
# Run from anywhere:  powershell -File packaging\windows\build.ps1
# Requires: pip install -r requirements.txt (PyInstaller included).

$ErrorActionPreference = 'Stop'

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot     = Split-Path -Parent (Split-Path -Parent $PackagingDir)

Write-Host "== Compiling .ui files ==" -ForegroundColor Cyan
python (Join-Path $RepoRoot 'tools\build_ui.py') --force
# $ErrorActionPreference = 'Stop' only catches failing PowerShell cmdlets,
# not a failing native executable - a non-zero exit here would otherwise be
# silently ignored and this script would carry on (and exit 0) as if
# nothing were wrong, letting a later step fail confusingly instead (e.g.
# Inno Setup complaining dist\ has no files, with no clue PyInstaller
# itself never ran successfully).
if ($LASTEXITCODE -ne 0) { throw "tools/build_ui.py failed (exit $LASTEXITCODE)" }

Write-Host "== Running PyInstaller ==" -ForegroundColor Cyan
pyinstaller (Join-Path $PackagingDir 'ap_log_plotter.spec') `
    --distpath (Join-Path $PackagingDir 'dist') `
    --workpath (Join-Path $PackagingDir 'build') `
    --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit $LASTEXITCODE)" }

Write-Host ""
Write-Host "Done: $(Join-Path $PackagingDir 'dist\AP Log Plotter\AP Log Plotter.exe')" -ForegroundColor Green
