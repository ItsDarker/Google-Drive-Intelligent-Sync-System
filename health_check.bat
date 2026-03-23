@echo off
REM ================================================================
REM       Google Drive Sync - Health Check (For Task Scheduler)
REM ================================================================

REM Change to script directory
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Log health check start
echo %date% %time% - Starting health check >> logs\health_check.log

REM Run health check PowerShell script
powershell.exe -ExecutionPolicy Bypass -File "%~dp0health_check.ps1" >> logs\health_check.log 2>&1

REM Log completion
if %errorlevel% == 0 (
    echo %date% %time% - Health check completed successfully >> logs\health_check.log
) else (
    echo %date% %time% - Health check failed with exit code %errorlevel% >> logs\health_check.log
)

REM End of script
exit /b %errorlevel%