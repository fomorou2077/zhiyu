# 知舆后端 API

## 环境要求
- Python 3.8+
- **ffmpeg**（视频语音转写必需）

### ffmpeg 安装说明

#### Windows
1. 下载地址：https://ffmpeg.org/download.html
2. 推荐使用 winget 安装：
   ```
   winget install ffmpeg
   ```
   或使用 Chocolatey：
   ```
   choco install ffmpeg
   ```
3. 安装完成后在命令行执行 `ffmpeg -version` 验证。

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

## 安装运行
1. 创建并激活虚拟环境
   - `py -3.8 -m venv .venv`
   - `.\.venv\Scripts\python -m pip install --upgrade pip`
2. 安装依赖
   - `.\.venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.org/simple`
3. 配置环境变量
   - 复制 `.env.example` 为 `.env`，填入阿里云百炼 API Key
4. 初始化数据库
   - `.\.venv\Scripts\python -c "import asyncio; from app.database import engine, Base; from app import models; async def init(): async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all); asyncio.run(init())"`
5. 启动服务
   - `.\.venv\Scripts\python run.py`
6. API 文档
   - `http://127.0.0.1:8000/docs`

## 功能
- 用户注册/登录
- 视频上传与情绪分析
- AI对话助手“知知”
- 历史记录查询
- 个人情绪趋势

## 多模态分析（可选功能）

### 简介
多模态分析模块 `app/services/multimodal_emotion.py` 提供基于视觉、音频、文本三模态融合的视频情绪分析能力。

### 依赖安装
```bash
pip install torch torchvision torchaudio transformers opencv-python librosa pandas tqdm
```

> 注意：PyTorch 较大（约2GB），安装时间较长。如果不需要多模态分析，可以跳过此步骤。

### 模型训练流程

#### 步骤 1：准备视频数据
1. 将视频文件放入 `uploads/` 目录
2. 运行数据准备脚本：
```bash
python scripts/prepare_data.py
# 或使用 Windows 脚本
run_prepare_data.bat
```

可选参数：
```bash
--data-dir uploads        # 指定视频目录
--max-videos 100         # 最多处理视频数量
--force                   # 强制重新处理
--skip-emotion           # 跳过情绪分析（使用模拟标签）
```

#### 步骤 2：训练模型
```bash
python scripts/train_multimodal.py
# 或使用 Windows 脚本
run_train.bat
```

可选参数：
```bash
--batch-size 4           # 批次大小（根据显存调整）
--epochs 30              # 训练轮数
--lr 0.0001             # 学习率
--resume path/to/checkpoint.pth  # 从检查点恢复训练
```

#### 步骤 3：测试模型
训练完成后，重启后端即可自动使用训练好的模型进行分析。

---

### 使用方法

#### API 调用
上传视频时添加 `use_multimodal=true` 参数即可启用多模态分析：

```bash
# 使用多模态分析
curl -X POST "http://localhost:8000/videos/upload?use_multimodal=true" -F "file=@video.mp4"

# 使用原有文本分析（默认）
curl -X POST "http://localhost:8000/videos/upload" -F "file=@video.mp4"
```

#### Python 调用
```python
from app.services.multimodal_emotion import analyze_video_multimodal, get_model_info

# 分析视频
result = await analyze_video_multimodal("path/to/video.mp4")

# 获取模型信息
info = get_model_info()
print(info)
```

### 模型结构
```
MultiModalEmotionModel
├── VisualEncoder (ResNet50) - 视觉特征提取
├── AudioEncoder (Wav2Vec2) - 音频特征提取
├── TextEncoder (BERT) - 文本特征提取
└── CrossModalAttention - 跨模态注意力融合
```

### 文件结构
```
项目目录/
├── scripts/
│   ├── prepare_data.py     # 数据准备脚本
│   └── train_multimodal.py # 模型训练脚本
├── data/
│   └── processed/          # 处理后的数据
│       ├── metadata.csv    # 数据索引
│       └── {video_id}/     # 每个视频的特征
│           ├── frames.pt   # 视频帧
│           ├── audio.pt    # 音频
│           ├── text.txt    # 文本
│           └── labels.json # 标签
├── models/
│   ├── multimodal_emotion.pth    # 训练好的模型权重
│   └── training_history.json       # 训练历史
├── app/services/
│   ├── multimodal_emotion.py      # 多模态分析服务
│   └── video_dataset.py            # Dataset 类
└── run_*.bat                      # Windows 运行脚本
```

### 当前状态
- 数据预处理完成（帧提取、音频提取）
- Dataset 和 DataLoader 已实现
- 训练脚本已完成
- 需要收集视频数据并训练模型

### 模型权重
训练好的模型权重存放于：`models/multimodal_emotion.pth`
