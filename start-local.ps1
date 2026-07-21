$ErrorActionPreference = "Continue"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logPath = Join-Path $projectDir "start-local.log"
Set-Location $projectDir

try {
    Start-Transcript -Path $logPath -Force | Out-Null
    Write-Host "Taiwan Chip Rotation - Local Launcher" -ForegroundColor Cyan
    Write-Host "Project: $projectDir"

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $usePyLauncher = $false
    if (-not $pythonCommand) {
        $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
        $usePyLauncher = $true
    }
    if (-not $pythonCommand) {
        throw "Python was not found. Install Python from https://www.python.org/downloads/ and enable Add Python to PATH."
    }

    Write-Host "Python: $($pythonCommand.Source)"
    if ($usePyLauncher) {
        & $pythonCommand.Source -3 -c "import streamlit, pandas, plotly, openpyxl, pyarrow" 2>$null
    }
    else {
        & $pythonCommand.Source -c "import streamlit, pandas, plotly, openpyxl, pyarrow" 2>$null
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing required packages for the current user..." -ForegroundColor Yellow
        if ($usePyLauncher) {
            & $pythonCommand.Source -3 -m pip install --user -r (Join-Path $projectDir "requirements.txt")
        }
        else {
            & $pythonCommand.Source -m pip install --user -r (Join-Path $projectDir "requirements.txt")
        }
        if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }
    }

    Write-Host "Starting the website..." -ForegroundColor Green
    Write-Host "The browser should open at http://localhost:8501"
    Write-Host "Keep this window open. Press Ctrl+C to stop the website."
    if ($usePyLauncher) {
        & $pythonCommand.Source -3 -m streamlit run (Join-Path $projectDir "app.py") --server.address localhost --server.port 8501
    }
    else {
        & $pythonCommand.Source -m streamlit run (Join-Path $projectDir "app.py") --server.address localhost --server.port 8501
    }
    if ($LASTEXITCODE -ne 0) { throw "Streamlit stopped with exit code $LASTEXITCODE." }
    Stop-Transcript | Out-Null
    exit 0
}
catch {
    Write-Host ""
    Write-Host "STARTUP ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Diagnostic log: $logPath" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
