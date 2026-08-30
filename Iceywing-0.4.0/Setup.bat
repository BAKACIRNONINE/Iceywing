@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
if errorlevel 1 (
  echo.
  echo Setup failed. See the error and log path above.
  pause
)
