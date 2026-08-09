@echo off
chcp 65001 >nul
title 知舆 - 预测服务启动器

echo.
echo ========================================
echo       知舆 AI 预测服务启动器
echo ========================================
echo.

REM 获取当前脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM 检查虚拟环境
if exist ".venv\Scripts\python.exe" (
    echo [1/2] 检测到虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
    echo [OK] 虚拟环境已激活
) else (
    echo [警告] 未检测到虚拟环境，使用系统 Python
)

REM 检查并安装缺失的包
echo.
echo [2/2] 检查依赖包...
python -c "import flask" 2>nul
if errorlevel 1 (
    echo [安装] 缺少 flask，正在安装...
    pip install flask flask-cors httpx -i https://mirrors.aliyun.com/pypi/simple/
)

echo.
echo ========================================
echo  启动预测后端服务 (端口 5000)...
echo ========================================
echo.
echo 按 Ctrl+C 可停止服务
echo.

REM 启动预测后端
python predict_app.py

pause
