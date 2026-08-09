@echo off
chcp 65001 > nul
echo ================================================
echo 多模态分析 - 数据准备脚本
echo ================================================
echo.

:: 检查虚拟环境
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

:: 检查是否安装了 PyTorch
echo [1/3] 检查依赖...
%PYTHON% -c "import torch; print(f"  PyTorch: {torch.__version__}")" 2>nul
if errorlevel 1 (
    echo [警告] PyTorch 未安装，请先运行:
    echo   pip install torch torchvision torchaudio transformers opencv-python librosa pandas tqdm
    echo.
    echo 或者使用 CPU 版本:
    echo   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    echo.
)

echo [2/3] 检查视频目录...
if not exist "uploads" (
    echo [警告] uploads 目录不存在，正在创建...
    mkdir uploads
    echo [提示] 请将视频文件放入 uploads 目录
)

echo [3/3] 创建输出目录...
if not exist "data" mkdir data
if not exist "data\processed" mkdir data\processed

echo.
echo ================================================
echo 开始数据准备
echo ================================================
echo.

:: 运行数据准备脚本
%PYTHON% scripts/prepare_data.py %*

echo.
echo ================================================
echo 数据准备完成！
echo.
echo 提示:
echo   - 处理后的数据保存在 data\processed 目录
echo   - 使用 --force 参数可以重新处理已存在的视频
echo   - 使用 --data-dir 参数指定其他视频目录
echo.
echo 下一步: python scripts/train_multimodal.py
echo ================================================

pause
