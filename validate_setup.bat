@echo off
echo ================================================================
echo         Google Drive Production Sync - Setup Validator
echo ================================================================
echo.
echo This will validate your environment before the first sync:
echo.
echo Checks performed:
echo  ✓ Python version and packages
echo  ✓ Configuration files
echo  ✓ Credentials setup
echo  ✓ Directory permissions
echo  ✓ Disk space
echo  ✓ Internet connectivity
echo.
echo Press any key to start validation...
pause

echo.
python validate_setup.py

echo.
echo ================================================================
echo                    Validation Complete
echo ================================================================
echo.
echo If all checks passed, you're ready to sync!
echo If any checks failed, fix the issues and run this again.
echo.
pause