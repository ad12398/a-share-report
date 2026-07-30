@echo off
:: A股量化报告 — 定时任务执行脚本
:: 用法: run_report.bat [0925|1030|1130|1400|1500]
:: 不带参数则自动判断当前时段

setlocal enabledelayedexpansion

cd /d C:\a-share-report

:: GitHub Token（从环境变量读取，用 setx GH_TOKEN "xxx" 设置）

:: 日志目录
set LOG_DIR=C:\a-share-report\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: 日志文件名（按日期）
set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\report_%TODAY%.log

echo [%date% %time%] === 报告定时任务触发 === >> "%LOG_FILE%"

:: 运行部署脚本
python deploy.py %1 >> "%LOG_FILE%" 2>&1

:: 记录退出码
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] 完成, exit=%EXIT_CODE% >> "%LOG_FILE%"

exit /b %EXIT_CODE%
