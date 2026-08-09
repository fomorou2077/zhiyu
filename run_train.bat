@echo off
chcp 65001 > nul
echo ================================================
echo 多模态分析 - 模型训练脚本
echo ================================================
echo.

:: 检查虚拟环境
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

:: 检查依赖
echo [1/3] 检查依赖...
%PYTHON% -c "import torch; print(f"  PyTorch: {torch.__version__}")" 2>nul
if errorlevel 1 (
    echo [错误] PyTorch 未安装，请先安装依赖:
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

:: 检查数据
echo [2/3] 检查训练数据...
if not exist "data\processed\metadata.csv" (
    echo [错误] 训练数据不存在！
    echo.
    echo 请先运行数据准备脚本:
    echo   python scripts/prepare_data.py
    echo.
    pause
    exit /b 1
)

:: 统计样本数
for /f %%i in ('find /c /v "" ^< data\processed\metadata.csv') do set COUNT=%%i
set /a DATA_COUNT=%COUNT%-1
echo   找到 %DATA_COUNT% 个训练样本

:: 创建模型目录
echo [3/3] 创建模型目录...
if not exist "models" mkdir models

echo.
echo ================================================
echo 开始训练
echo ================================================
echo.
echo 配置:
echo   - 批次大小: 4 (可使用 --batch-size 参数调整)
echo   - 训练轮数: 30 (可使用 --epochs 参数调整)
echo   - 学习率: 1e-4
echo.
echo 模型将保存到: models\multimodal_emotion.pth
echo.
echo ================================================
echo.

:: 运行训练脚本
%PYTHON% scripts/train_multimodal.py %*

echo.
echo ================================================
echo 训练完成！
echo.
echo 提示:
echo   - 模型权重: models\multimodal_emotion.pth
echo   - 训练历史: models\training_history.json
echo   - 使用 --resume 继续训练
echo   - 使用 --epochs 100 增加训练轮数
echo.
echo 下一步: 重启后端，上传视频测试多模态分析
echo ================================================

pause
