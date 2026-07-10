# AP Log Plotter installer for Windows 11.
#
# - Installs Python 3 (via winget) if it isn't already on PATH.
# - Installs/updates the packages in requirements.txt.
# - Adds a "AP Log Plotter" shortcut to the Start Menu so the app shows up
#   in Windows search.
#
# Run by double-clicking install_windows.bat (which launches this script),
# or directly with:  powershell -ExecutionPolicy Bypass -File install_windows.ps1

$ErrorActionPreference = 'Stop'

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot     = Split-Path -Parent $InstallerDir
$GuiScript    = Join-Path $RepoRoot 'src\LogPlotterGUI.py'
$Requirements = Join-Path $RepoRoot 'requirements.txt'

function Test-CommandExists($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host "== AP Log Plotter installer ==" -ForegroundColor Cyan

# 1. Python -----------------------------------------------------------------
$python = $null
if (Test-CommandExists 'py') {
    $python = 'py'
} elseif (Test-CommandExists 'python') {
    $python = 'python'
}

if (-not $python) {
    Write-Host "Python not found - installing via winget..."
    if (-not (Test-CommandExists 'winget')) {
        throw "winget is not available on this machine. Install Python manually from https://www.python.org/downloads/windows/ (check 'Add python.exe to PATH' during setup), then re-run this installer."
    }

    winget install -e --id Python.Python.3.12 --scope machine --accept-package-agreements --accept-source-agreements

    # Refresh PATH for this process so the freshly installed python is visible
    # without having to open a new shell.
    $machinePath = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path    = "$machinePath;$userPath"

    if (Test-CommandExists 'py') { $python = 'py' }
    elseif (Test-CommandExists 'python') { $python = 'python' }

    if (-not $python) {
        throw "Python was installed but isn't on PATH yet in this window. Close this window, open a new PowerShell/terminal, and re-run install_windows.bat."
    }
}

Write-Host "Using Python: $(& $python --version)"

# 2. Requirements -------------------------------------------------------------
Write-Host "Installing/upgrading required packages..."
& $python -m pip install --upgrade pip
& $python -m pip install -r $Requirements

# 3. Start Menu shortcut (makes the app searchable) --------------------------
Write-Host "Creating Start Menu shortcut..."

$pyExe = (& $python -c "import sys; print(sys.executable)").Trim()
$pythonwPath = $pyExe -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonwPath)) {
    $pythonwPath = $pyExe
}

$startMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$shortcutPath = Join-Path $startMenuDir 'AP Log Plotter.lnk'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = '"' + $GuiScript + '"'
$shortcut.WorkingDirectory = $RepoRoot
$shortcut.Description = 'AP Log Plotter'
$shortcut.IconLocation = $pythonwPath
$shortcut.Save()

Write-Host ""
Write-Host "Done! Press the Windows key and type 'AP Log Plotter' to launch it." -ForegroundColor Green
