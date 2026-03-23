@echo off
REM ===================================================================
REM INTELLIGENT SYNC - Content-Based Synchronization
REM ===================================================================
REM This script runs the enhanced Drive sync with intelligent features:
REM - File rename detection (no duplicate downloads)
REM - Content-based comparison (only downloads changed content)
REM - Daily change logging
REM - Automatic cleanup of old renamed files
REM ===================================================================

echo.
echo ================================================================================
echo GOOGLE DRIVE INTELLIGENT SYNC
echo ================================================================================
echo.
echo This sync uses content analysis to:
echo   - Detect renamed files (moves instead of re-downloading)
echo   - Compare file signatures (skips unchanged content)
echo   - Log daily changes with detailed comparisons
echo   - Clean up duplicates automatically
echo.
echo ================================================================================
echo.

pause

echo.
echo Starting intelligent sync...
echo.

python enhanced_drive_sync.py --mode intelligent

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ================================================================================
    echo SYNC COMPLETED SUCCESSFULLY
    echo ================================================================================
    echo.
    echo Check the logs directory for:
    echo   - Detailed sync log: logs\drive_sync_*.log
    echo   - Daily changes (JSON): logs\daily_changes_*.json
    echo   - Daily changes (Text): logs\daily_changes_*.txt
    echo   - File signatures: state\file_signatures.json
    echo.
) else (
    echo.
    echo ================================================================================
    echo SYNC FAILED - Exit Code: %ERRORLEVEL%
    echo ================================================================================
    echo.
    echo Please check the logs directory for error details.
    echo.
)

pause
