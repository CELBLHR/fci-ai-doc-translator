@echo off
chcp 65001 >nul
title Admin密码重置工具

echo.
echo ========================================
echo 🔐 PPT翻译系统 - Admin密码重置工具
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python
    echo.
    pause
    exit /b 1
)

:: 检查是否有参数
if "%1"=="" (
    echo 📝 选择重置方式:
    echo.
    echo 1. 重置为默认密码 ^(admin123^)
    echo 2. 设置自定义密码
    echo 3. 交互式修改密码
    echo.
    set /p choice="请选择 (1-3): "
    
    if "!choice!"=="1" (
        echo.
        echo 🔄 重置为默认密码...
        python reset_admin.py
    ) else if "!choice!"=="2" (
        echo.
        set /p custom_password="请输入新密码: "
        if "!custom_password!"=="" (
            echo ❌ 密码不能为空
            pause
            exit /b 1
        )
        python reset_admin.py "!custom_password!"
    ) else if "!choice!"=="3" (
        echo.
        echo 🔧 启动交互式修改工具...
        python change_admin_password.py
    ) else (
        echo ❌ 无效选择
        pause
        exit /b 1
    )
) else (
    :: 有参数，直接使用
    echo 🔄 使用指定密码重置...
    python reset_admin.py "%1"
)

echo.
echo ========================================
if errorlevel 1 (
    echo ❌ 操作失败！
) else (
    echo ✅ 操作完成！
)
echo ========================================
echo.
pause
