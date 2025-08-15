@echo off
REM 设置用户为管理员的批处理脚本
REM 使用方法：set_admin.bat <user_id>

IF "%1"=="" (
    echo 错误: 请提供用户ID
    echo 使用方法: set_admin.bat ^<user_id^>
    exit /b 1
)

echo 正在将用户ID %1 设置为管理员...
python %~dp0set_admin.py %*
IF %ERRORLEVEL% NEQ 0 (
    echo 操作失败!
    exit /b 1
) ELSE (
    echo 操作成功完成!
    exit /b 0
) 