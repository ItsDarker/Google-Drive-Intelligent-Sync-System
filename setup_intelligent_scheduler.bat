@echo off
REM ===================================================================
REM SETUP INTELLIGENT SYNC SCHEDULER
REM ===================================================================
REM Creates a Windows Task Scheduler task to run intelligent sync daily
REM ===================================================================

setlocal EnableDelayedExpansion

echo.
echo ================================================================================
echo SETUP INTELLIGENT SYNC SCHEDULER
echo ================================================================================
echo.
echo This will create a scheduled task to run intelligent sync automatically.
echo.
echo Task Configuration:
echo   - Name: GoogleDriveIntelligentSync
echo   - Schedule: Daily at 2:00 AM
echo   - Script: sync_intelligent_silent.bat
echo   - User: %USERNAME%
echo.
echo ================================================================================
echo.

pause

REM Get the current directory
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%sync_intelligent_silent.bat

echo.
echo Creating scheduled task...
echo.

REM Delete old task if it exists
schtasks /query /tn "GoogleDriveIntelligentSync" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Removing existing task...
    schtasks /delete /tn "GoogleDriveIntelligentSync" /f
)

REM Create new task
schtasks /create ^
    /tn "GoogleDriveIntelligentSync" ^
    /tr "\"%SCRIPT_PATH%\"" ^
    /sc daily ^
    /st 02:00 ^
    /rl highest ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ================================================================================
    echo SCHEDULER SETUP SUCCESSFUL
    echo ================================================================================
    echo.
    echo Task created: GoogleDriveIntelligentSync
    echo Schedule: Daily at 2:00 AM
    echo Script: %SCRIPT_PATH%
    echo.
    echo You can:
    echo   - View the task in Task Scheduler: taskschd.msc
    echo   - Run it manually: schtasks /run /tn "GoogleDriveIntelligentSync"
    echo   - Check logs at: %SCRIPT_DIR%logs\scheduler.log
    echo.
    echo ================================================================================
    echo.
) else (
    echo.
    echo ================================================================================
    echo SCHEDULER SETUP FAILED
    echo ================================================================================
    echo.
    echo Error Code: %ERRORLEVEL%
    echo.
    echo This usually means:
    echo   1. You need to run this script as Administrator
    echo   2. Task Scheduler service is not running
    echo.
    echo Please try running this batch file as Administrator.
    echo.
    echo ================================================================================
    echo.
)

pause
