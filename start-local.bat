@echo off
cd /d "%~dp0"
title Taiwan Chip Rotation - Local Launcher

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"
set "RESULT=%ERRORLEVEL%"

echo.
if not "%RESULT%"=="0" (
  echo Startup failed. Please send the start-local.log file for diagnosis.
) else (
  echo The local website has stopped.
)
echo.
pause
exit /b %RESULT%
