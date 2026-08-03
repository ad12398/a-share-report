@echo off
:: A-share report - scheduled task launcher
:: Usage: run_report.bat [0925|1030|1130|1400|1500]

setlocal enabledelayedexpansion

cd /d C:\a-share-report

set LOG_DIR=C:\a-share-report\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\report_%TODAY%.log

echo [%date% %time%] === scheduled task triggered === >> "%LOG_FILE%"

python deploy.py %1 >> "%LOG_FILE%" 2>&1

set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] done, exit=%EXIT_CODE% >> "%LOG_FILE%"

exit /b %EXIT_CODE%
