@echo off
chcp 65001 >nul
title 知舆 - 功能测试

echo.
echo ========================================
echo       知舆 功能测试脚本
echo ========================================
echo.

REM 获取当前脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM 检查虚拟环境
if exist ".venv\Scripts\python.exe" (
    echo [1/5] 激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo [错误] 未检测到虚拟环境 .venv
    pause
    exit /b 1
)

echo [2/5] 启动后端服务（后台运行）...
start "知舆后端" python run.py

echo [3/5] 等待后端启动（10秒）...
timeout /t 10 /nobreak >nul

echo [4/5] 执行 API 测试...
echo.

REM 测试健康检查
echo === 测试 1: 健康检查 ===
curl -s http://localhost:8000/health
echo.

REM 测试监测 API（小红书链接）
echo.
echo === 测试 2: 监测 API - 小红书 ===
curl -s -X POST http://localhost:8000/monitor/fetch ^
  -H "Content-Type: application/json" ^
  -d "{\"url\": \"https://www.xiaohongshu.com/explore/1234567890abcdef\"}"
echo.

REM 测试监测 API（抖音链接）
echo.
echo === 测试 3: 监测 API - 抖音 ===
curl -s -X POST http://localhost:8000/monitor/fetch ^
  -H "Content-Type: application/json" ^
  -d "{\"url\": \"https://www.douyin.com/video/7234567890123456789\"}"
echo.

REM 测试监测 API（B站链接）
echo.
echo === 测试 4: 监测 API - B站 ===
curl -s -X POST http://localhost:8000/monitor/fetch ^
  -H "Content-Type: application/json" ^
  -d "{\"url\": \"https://www.bilibili.com/video/BV1xx411c7XD\"}"
echo.

REM 获取监测记录
echo.
echo === 测试 5: 获取监测记录 ===
curl -s http://localhost:8000/monitor/records
echo.

echo.
echo ========================================
echo       测试完成！
echo ========================================
echo.
echo 后端服务仍在运行，可在浏览器打开 index.html 测试前端
echo 按任意键关闭此窗口，后端服务继续运行
echo.
pause
