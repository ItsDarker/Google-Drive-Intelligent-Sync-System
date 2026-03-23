@echo off
REM ===================================================================
REM INTELLIGENT SYNC - Silent Mode (for Task Scheduler)
REM ===================================================================
REM This script runs intelligent sync without user interaction
REM Suitable for scheduled tasks
REM ===================================================================

setlocal

set LOG_FILE=logs\scheduler.log
set TIMESTAMP=%date% %time%

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Log start
echo %TIMESTAMP% - Starting intelligent sync >> %LOG_FILE%
echo Script: sync_intelligent_silent.bat, User: %USERNAME% >> %LOG_FILE%

REM Run intelligent sync
python enhanced_drive_sync.py --mode intelligent >> %LOG_FILE% 2>&1

REM Log completion
if %ERRORLEVEL% EQU 0 (
    echo %TIMESTAMP% - Intelligent sync completed successfully ^(Exit Code: 0^) >> %LOG_FILE%
    exit /b 0
) else (
    echo %TIMESTAMP% - Intelligent sync failed ^(Exit Code: %ERRORLEVEL%^) >> %LOG_FILE%
    exit /b %ERRORLEVEL%
)
