@echo off
chcp 65001 >nul
title 知舆 - 启动后端服务

echo.
echo ========================================
echo         知舆 后端服务启动器
echo ========================================
echo.

REM 获取当前脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM 获取当前脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM 检查虚拟环境
if exist ".venv\Scripts\python.exe" (
    echo [1/3] 检测到虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
    set PYTHON=.venv\Scripts\python.exe
) else (
    echo [提示] 未检测到虚拟环境，使用系统 Python
    echo [提示] 建议运行: python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    set PYTHON=python
)

REM 检查并安装缺失的包
echo.
echo [2/3] 检查依赖包...
%PYTHON% -c "import uvicorn; import fastapi" 2>nul
if errorlevel 1 (
    echo [安装] 缺少依赖包，正在从 requirements.txt 安装...
    pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
)

echo.
echo [3/3] 数据库将在首次请求时自动初始化...

echo.
echo ========================================
echo  启动主后端服务 (端口 8000)...
echo ========================================
echo.
echo 按 Ctrl+C 可停止服务
echo.

REM 启动主后端
%PYTHON% run.py

REM 如果上面失败，尝试备用启动方式
if errorlevel 1 (
    echo.
    echo [备用方式] 尝试直接运行...
    %PYTHON% -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
)

pause
