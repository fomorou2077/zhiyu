"""
多模态情绪分析服务

本模块提供基于视觉、音频、文本三模态融合的视频情绪分析能力。
为后续引入多模态特征融合模型做准备。

功能：
- 数据预处理：视频帧提取、音频提取、文本提取
- 模型结构：视觉编码器、音频编码器、文本编码器、跨模态注意力融合
- 统一分析接口：analyze_video_multimodal

当前状态：
- 模型部分使用预训练模型（ResNet50, Wav2Vec2, BERT）
- 因无训练权重，当前返回模拟结果
- 保留真实模型推理接口，可后续替换
"""

import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import numpy as np

# 可选依赖检查
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[警告] opencv-python 未安装，帧提取功能将使用模拟数据")

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("[警告] librosa 未安装，音频处理功能将使用模拟数据")

try:
    from transformers import BertTokenizer, BertModel, Wav2Vec2Model
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("[警告] transformers 未安装，文本编码器将使用模拟输出")

try:
    from torchvision import transforms, models
    TORCHVISION_AVAILABLE = True
except ImportError:
    TORCHVISION_AVAILABLE = False
    print("[警告] torchvision 未安装，视觉编码器将使用模拟输出")

from app.utils.logger import logger

# ============================================
# 配置常量
# ============================================

# 模型配置
MODEL_CONFIG = {
    "visual": {
        "backbone": "resnet50",
        "output_dim": 256,
        "pretrained": True,
    },
    "audio": {
        "backbone": "wav2vec2-base",
        "output_dim": 256,
        "pretrained": True,
    },
    "text": {
        "backbone": "bert-base-chinese",
        "output_dim": 256,
        "max_length": 128,
        "pretrained": True,
    },
    "fusion": {
        "hidden_dim": 256,
        "num_heads": 4,
        "num_emotions": 6,
    },
}

# 设备配置
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 模型权重路径
MODEL_DIR = Path(__file__).parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "multimodal_emotion.pth"


# ============================================
# 数据预处理函数
# ============================================

def extract_frames(video_path: str, target_frames: int = 16) -> torch.Tensor:
    """
    从视频文件中提取帧。

    Args:
        video_path: 视频文件路径
        target_frames: 目标提取帧数

    Returns:
        torch.Tensor: shape (1, T, 3, H, W) 的视频帧张量
    """
    if not CV2_AVAILABLE:
        logger.warning("OpenCV不可用，返回模拟帧数据")
        return torch.randn(1, target_frames, 3, 224, 224)

    try:
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames == 0:
            logger.warning("视频无帧: {}", video_path)
            return torch.randn(1, target_frames, 3, 224, 224)

        # 均匀采样帧
        indices = np.linspace(0, total_frames - 1, target_frames, dtype=int)

        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                # BGR to RGB，resize到224x224
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (224, 224))
                frames.append(frame)

        cap.release()

        # 填充到目标帧数
        while len(frames) < target_frames:
            frames.append(frames[-1] if frames else np.zeros((224, 224, 3), dtype=np.uint8))

        # 转换为张量 (T, H, W, C) -> (1, T, C, H, W)
        frames_array = np.stack(frames[:target_frames])
        frames_tensor = torch.from_numpy(frames_array).permute(0, 3, 1, 2).float() / 255.0

        logger.info("成功提取视频帧: {} -> {} 帧", video_path, target_frames)
        return frames_tensor

    except Exception as e:
        logger.error("提取视频帧失败: {} - {}", video_path, e)
        return torch.randn(1, target_frames, 3, 224, 224)


def extract_audio(video_path: str, target_length: int = 160000) -> torch.Tensor:
    """
    从视频文件中提取音频特征。

    Args:
        video_path: 视频文件路径
        target_length: 目标音频采样长度

    Returns:
        torch.Tensor: shape (1, target_length) 的音频张量
    """
    if not LIBROSA_AVAILABLE or not CV2_AVAILABLE:
        logger.warning("librosa/CV2不可用，返回模拟音频数据")
        return torch.randn(1, target_length)

    try:
        # 使用OpenCV提取音频（需要ffmpeg）
        import subprocess

        # 临时音频文件
        audio_path = video_path + ".wav"

        # 提取音频
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            audio_path
        ]
        subprocess.run(cmd, capture_output=True, check=False)

        # 加载音频
        audio, sr = librosa.load(audio_path, sr=16000)

        # 截断或填充到目标长度
        if len(audio) < target_length:
            audio = np.pad(audio, (0, target_length - len(audio)))
        else:
            audio = audio[:target_length]

        # 清理临时文件
        try:
            os.remove(audio_path)
        except:
            pass

        logger.info("成功提取音频: {} -> {} 采样点", video_path, target_length)
        return torch.from_numpy(audio).float().unsqueeze(0)

    except Exception as e:
        logger.error("提取音频失败: {} - {}", video_path, e)
        return torch.randn(1, target_length)


def extract_text(video_path: str) -> str:
    """
    从视频中提取文本（语音转文字）。

    当前版本返回模拟文本。
    后续可接入语音识别服务（如Whisper、阿里云ASR）。

    Args:
        video_path: 视频文件路径

    Returns:
        str: 提取的文本内容
    """
    # TODO: 接入真实语音识别服务
    # 示例：使用 Whisper
    # import whisper
    # model = whisper.load_model("base")
    # result = model.transcribe(video_path)
    # return result["text"]

    logger.debug("当前使用模拟文本，实际应接入语音识别服务")
    return ""


def preprocess_video(video_path: str) -> Tuple[torch.Tensor, torch.Tensor, str]:
    """
    预处理视频，提取所有模态数据。

    Args:
        video_path: 视频文件路径

    Returns:
        Tuple[frames, audio, text]: 预处理后的数据
    """
    logger.info("开始预处理视频: {}", video_path)

    frames = extract_frames(video_path)
    audio = extract_audio(video_path)
    text = extract_text(video_path)

    logger.info("视频预处理完成: frames={}, audio={}, text_len={}",
                frames.shape, audio.shape, len(text))

    return frames, audio, text


# ============================================
# 模型结构定义
# ============================================

class VisualEncoder(nn.Module):
    """
    视觉编码器

    使用预训练ResNet50作为backbone，提取视频帧特征。
    """

    def __init__(self, output_dim: int = 256):
        super().__init__()
        self.output_dim = output_dim

        if TORCHVISION_AVAILABLE:
            self.backbone = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
            self.backbone.fc = nn.Identity()
            self.pool = nn.AdaptiveAvgPool2d((1, 1))
            self.projector = nn.Linear(2048, output_dim)

            # 冻结backbone
            for param in self.backbone.parameters():
                param.requires_grad = False
        else:
            # 回退到线性层
            self.backbone = None
            self.projector = nn.Linear(512, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, T, 3, H, W) 视频帧

        Returns:
            torch.Tensor: (batch, output_dim) 视觉特征
        """
        if self.backbone is None:
            # 模拟输出
            return torch.randn(x.size(0), self.output_dim)

        batch, T, C, H, W = x.shape
        x = x.view(batch * T, C, H, W)

        x = self.backbone(x)
        x = self.pool(x).squeeze(-1).squeeze(-1)
        x = x.view(batch, T, -1).mean(dim=1)
        x = self.projector(x)

        return x


class AudioEncoder(nn.Module):
    """
    音频编码器

    使用预训练Wav2Vec2作为backbone，提取音频特征。
    """

    def __init__(self, output_dim: int = 256):
        super().__init__()
        self.output_dim = output_dim

        if TRANSFORMERS_AVAILABLE:
            try:
                self.backbone = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base")
                self.pool = nn.AdaptiveAvgPool1d(1)
                self.projector = nn.Linear(768, output_dim)

                for param in self.backbone.parameters():
                    param.requires_grad = False
            except Exception as e:
                logger.warning("无法加载Wav2Vec2模型: {}", e)
                self.backbone = None
                self.projector = nn.Linear(512, output_dim)
        else:
            self.backbone = None
            self.projector = nn.Linear(512, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, time) 音频波形

        Returns:
            torch.Tensor: (batch, output_dim) 音频特征
        """
        if self.backbone is None:
            return torch.randn(x.size(0), self.output_dim)

        outputs = self.backbone(x).last_hidden_state
        x = outputs.transpose(1, 2)
        x = nn.functional.adaptive_avg_pool1d(x, 1).squeeze(-1)
        x = self.projector(x)

        return x


class TextEncoder(nn.Module):
    """
    文本编码器

    使用预训练BERT作为backbone，提取文本特征。
    """

    def __init__(self, output_dim: int = 256):
        super().__init__()
        self.output_dim = output_dim
        self.max_length = 128

        if TRANSFORMERS_AVAILABLE:
            try:
                self.tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
                self.backbone = BertModel.from_pretrained("bert-base-chinese")
                self.projector = nn.Linear(768, output_dim)

                for param in self.backbone.parameters():
                    param.requires_grad = False
            except Exception as e:
                logger.warning("无法加载BERT模型: {}", e)
                self.tokenizer = None
                self.backbone = None
                self.projector = nn.Linear(512, output_dim)
        else:
            self.tokenizer = None
            self.backbone = None
            self.projector = nn.Linear(512, output_dim)

    def forward(self, text: str = None, input_ids: torch.Tensor = None, attention_mask: torch.Tensor = None) -> torch.Tensor:
        """
        前向传播。

        支持两种模式:
        1. text: str - 直接输入文本字符串
        2. input_ids + attention_mask - 输入已 tokenize 的张量（用于训练）

        Returns:
            torch.Tensor: (batch, output_dim) 文本特征
        """
        batch_size = 1

        if self.backbone is None:
            return torch.randn(batch_size, self.output_dim)

        if input_ids is not None:
            # 训练模式：使用已 tokenize 的输入
            inputs = {
                'input_ids': input_ids,
                'attention_mask': attention_mask
            }
        elif text is not None:
            # 推理模式：直接输入文本
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length
            )
            # 将输入移到设备
            device = next(self.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
        else:
            return torch.randn(batch_size, self.output_dim)

        outputs = self.backbone(**inputs)
        cls_emb = outputs.last_hidden_state[:, 0, :]
        x = self.projector(cls_emb)

        return x


class CrossModalAttention(nn.Module):
    """
    跨模态注意力融合模块

    将视觉、音频、文本三模态特征进行注意力融合。
    """

    def __init__(self, hidden_dim: int = 256, num_classes: int = 6):
        super().__init__()

        self.attn = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=4,
            batch_first=True
        )

        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, num_classes)
        )

    def forward(self, v: torch.Tensor, a: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        """
        Args:
            v: (batch, hidden_dim) 视觉特征
            a: (batch, hidden_dim) 音频特征
            t: (batch, hidden_dim) 文本特征

        Returns:
            torch.Tensor: (batch, num_classes) 情绪分类 logits
        """
        seq = torch.stack([v, a, t], dim=1)  # (batch, 3, hidden_dim)
        attn_out, _ = self.attn(seq, seq, seq)
        fused = attn_out.reshape(attn_out.size(0), -1)
        return self.classifier(fused)


class MultiModalEmotionModel(nn.Module):
    """
    多模态情绪分析模型

    整合视觉、音频、文本三个编码器和一个跨模态注意力融合模块。
    """

    def __init__(self):
        super().__init__()

        self.visual_encoder = VisualEncoder()
        self.audio_encoder = AudioEncoder()
        self.text_encoder = TextEncoder()
        self.fusion = CrossModalAttention()

        # 情绪标签
        self.emotion_labels = ["joy", "sadness", "anger", "calm", "anxiety", "expectation"]

    def forward(
        self,
        frames: torch.Tensor = None,
        audio: torch.Tensor = None,
        text: str = None,
        input_ids: torch.Tensor = None,
        attention_mask: torch.Tensor = None
    ) -> torch.Tensor:
        """
        前向传播。

        支持两种模式:
        1. 推理模式: frames, audio, text (字符串)
        2. 训练模式: frames, audio, input_ids, attention_mask (张量)

        Args:
            frames: 视频帧 (batch, T, 3, H, W)
            audio: 音频波形 (batch, time)
            text: 输入文本字符串（推理用）
            input_ids: tokenized 文本 IDs (batch, seq_len)
            attention_mask: attention mask (batch, seq_len)

        Returns:
            torch.Tensor: (batch, 6) 情绪分数
        """
        # 视觉特征
        if frames is not None:
            v = self.visual_encoder(frames)
        else:
            v = torch.randn(1, 256)

        # 音频特征
        if audio is not None:
            a = self.audio_encoder(audio)
        else:
            a = torch.randn(1, 256)

        # 文本特征
        if input_ids is not None and attention_mask is not None:
            # 训练模式
            t = self.text_encoder(input_ids=input_ids, attention_mask=attention_mask)
        elif text is not None:
            # 推理模式
            t = self.text_encoder(text=text)
        else:
            t = torch.randn(1, 256)

        # 跨模态融合
        logits = self.fusion(v, a, t)

        return logits

    def predict(self, frames: torch.Tensor, audio: torch.Tensor, text: str) -> Dict[str, float]:
        """
        推理预测接口。

        Args:
            frames: 视频帧
            audio: 音频波形
            text: 文本

        Returns:
            Dict: 情绪分数字典 (0-10)
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(frames, audio, text)
            # 使用 softmax 转换为概率，然后缩放到 0-10
            probs = torch.softmax(logits, dim=-1)
            emotions = {
                label: round(float(probs[0, i].item() * 10), 2)
                for i, label in enumerate(self.emotion_labels)
            }
        return emotions

    def load_weights(self, path: str):
        """加载模型权重"""
        if os.path.exists(path):
            state_dict = torch.load(path, map_location=DEVICE, weights_only=True)
            self.load_state_dict(state_dict)
            logger.info("成功加载模型权重: {}", path)
        else:
            logger.warning("模型权重文件不存在: {}，将使用预训练模型", path)


# ============================================
# 全局模型实例（延迟加载）
# ============================================

_model_instance: Optional[MultiModalEmotionModel] = None


def _load_trained_model() -> Optional[MultiModalEmotionModel]:
    """
    加载训练好的模型

    Returns:
        加载成功的模型实例，或 None
    """
    global _model_instance

    model_path = Path("models/multimodal_emotion.pth")

    if not model_path.exists():
        return None

    try:
        if _model_instance is None:
            logger.info("加载训练好的多模态情绪分析模型...")
            _model_instance = MultiModalEmotionModel()

            # 加载权重
            state_dict = torch.load(model_path, map_location='cpu', weights_only=True)
            _model_instance.load_state_dict(state_dict)
            _model_instance.eval()

            logger.info("模型加载成功: {}", model_path)

        return _model_instance

    except Exception as e:
        logger.error("模型加载失败: {}", e)
        _model_instance = None
        return None


def get_model() -> MultiModalEmotionModel:
    """获取或创建全局模型实例"""
    global _model_instance

    if _model_instance is None:
        logger.info("初始化多模态情绪分析模型...")
        _model_instance = MultiModalEmotionModel()

        # 尝试加载训练好的权重
        if MODEL_PATH.exists():
            _model_instance.load_weights(str(MODEL_PATH))
        else:
            logger.info("未找到训练权重文件 {}，使用预训练模型（模拟输出）", MODEL_PATH)

    return _model_instance


# ============================================
# 统一分析接口
# ============================================

async def analyze_video_multimodal(
    video_path: str,
    use_simulation: bool = None
) -> Dict[str, Any]:
    """
    多模态视频情绪分析主函数。

    自动检测是否有训练好的模型：
    - 有模型：使用真实模型推理
    - 无模型：返回模拟结果

    Args:
        video_path: 视频文件路径
        use_simulation: 是否使用模拟结果（可选，默认自动检测）

    Returns:
        Dict: 情绪分析结果
    """
    logger.info("=" * 50)
    logger.info("开始多模态视频分析: {}", video_path)

    # 1. 数据预处理
    frames, audio, text = preprocess_video(video_path)

    # 2. 检测是否使用模拟模式
    model_path = Path("models/multimodal_emotion.pth")
    model_exists = model_path.exists()

    if use_simulation is None:
        # 自动检测：有模型就用真实推理，没有就用模拟
        use_simulation = not model_exists

    if use_simulation:
        logger.info("使用模拟分析模式（无训练权重）")
        # 模拟结果（无训练权重时使用）

        # 基于视频路径生成伪随机但稳定的模拟数据
        seed = hash(video_path) % 1000
        random.seed(seed)

        emotions = {
            "joy": round(random.uniform(3, 8), 1),
            "sadness": round(random.uniform(1, 5), 1),
            "anger": round(random.uniform(1, 4), 1),
            "calm": round(random.uniform(3, 7), 1),
            "anxiety": round(random.uniform(2, 6), 1),
            "expectation": round(random.uniform(3, 8), 1),
        }

        # 计算模拟风险分数
        risk_score = round(
            emotions["anger"] * 1.5 +
            emotions["anxiety"] * 1.3 +
            emotions["sadness"] * 1.0 -
            emotions["joy"] * 0.5 -
            emotions["calm"] * 0.5
        )
        risk_score = max(0, min(100, risk_score + 30))

        keywords = ["视频内容", "多模态分析", "模拟数据"]
        suggestions = "这是多模态分析框架的模拟结果，待模型训练后替换为真实推理结果。"
        category = "其他"

        result = {
            "emotions": emotions,
            "risk_score": risk_score,
            "keywords": keywords,
            "suggestions": suggestions,
            "category": category,
            "mode": "simulation",
        }

    else:
        # 真实模型推理
        logger.info("使用训练模型进行推理: {}", model_path)

        model = _load_trained_model()

        if model is None:
            logger.warning("模型加载失败，回退到模拟模式")
            return await analyze_video_multimodal(video_path, use_simulation=True)

        with torch.no_grad():
            emotions = model.predict(frames, audio, text)

        # 计算风险分数
        risk_score = _calculate_risk_score(emotions)

        # 根据风险分数判断内容类别
        if emotions["anger"] > 6 or emotions["anxiety"] > 7:
            category = "社会"
        elif emotions["sadness"] > 6:
            category = "情感"
        elif emotions["joy"] > 6:
            category = "娱乐"
        elif emotions["expectation"] > 6:
            category = "科技"
        else:
            category = "其他"

        keywords = _extract_keywords_from_emotions(emotions)
        suggestions = _generate_suggestions(emotions, risk_score)

        result = {
            "emotions": emotions,
            "risk_score": int(risk_score),
            "keywords": keywords,
            "suggestions": suggestions,
            "category": category,
            "mode": "model",
        }

    logger.info("多模态分析完成: risk_score={}, category={}, mode={}",
                result["risk_score"], result["category"], result.get("mode", "unknown"))
    logger.info("=" * 50)

    return result


def _calculate_risk_score(emotions: Dict[str, float]) -> float:
    """
    基于情绪分数计算风险评分。

    权重配置：
    - anger: 1.5 (愤怒权重最高)
    - anxiety: 1.3
    - sadness: 1.0
    - joy: -0.5 (积极情绪降低风险)
    - calm: -0.3
    - expectation: 0.0
    """
    weights = {
        "joy": -0.5,
        "sadness": 1.0,
        "anger": 1.5,
        "calm": -0.3,
        "anxiety": 1.3,
        "expectation": 0.0,
    }

    score = 50  # 基础分
    for emotion, value in emotions.items():
        score += weights.get(emotion, 0) * value

    return max(0, min(100, round(score, 1)))


def _extract_keywords_from_emotions(emotions: Dict[str, float]) -> List[str]:
    """
    根据情绪分数提取关键词

    Args:
        emotions: 情绪分数字典

    Returns:
        关键词列表
    """
    keywords = []

    # 基于高权重情绪添加关键词
    if emotions.get("anger", 0) > 6:
        keywords.extend(["争议", "愤怒", "冲突"])
    elif emotions.get("anger", 0) > 4:
        keywords.append("负面情绪")

    if emotions.get("anxiety", 0) > 6:
        keywords.extend(["焦虑", "担忧", "不确定性"])
    elif emotions.get("anxiety", 0) > 4:
        keywords.append("焦虑情绪")

    if emotions.get("sadness", 0) > 6:
        keywords.extend(["悲伤", "负面", "低落"])
    elif emotions.get("sadness", 0) > 4:
        keywords.append("悲伤情绪")

    if emotions.get("joy", 0) > 6:
        keywords.extend(["积极", "正面", "乐观"])

    if emotions.get("calm", 0) > 6:
        keywords.extend(["平静", "理性", "客观"])

    if emotions.get("expectation", 0) > 6:
        keywords.extend(["期待", "希望", "憧憬"])

    # 去重并限制数量
    keywords = list(set(keywords))[:5]

    if not keywords:
        keywords = ["情绪分析"]

    return keywords


def _generate_suggestions(emotions: Dict[str, float], risk_score: float) -> str:
    """
    根据情绪分析结果生成建议

    Args:
        emotions: 情绪分数字典
        risk_score: 风险分数

    Returns:
        建议文本
    """
    suggestions = []

    # 高风险建议
    if risk_score >= 70:
        if emotions.get("anger", 0) > 6:
            suggestions.append("内容包含较强的愤怒情绪，建议审核是否涉及不当言论。")
        elif emotions.get("anxiety", 0) > 6:
            suggestions.append("内容可能引发观众焦虑情绪，建议评估内容适当性。")
        elif emotions.get("sadness", 0) > 6:
            suggestions.append("内容情绪较为消极，可能影响观众心态。")
        else:
            suggestions.append("内容风险较高，建议仔细审核后再发布。")

    # 中风险建议
    elif risk_score >= 40:
        if emotions.get("anger", 0) > 4:
            suggestions.append("内容包含争议性观点，建议谨慎措辞。")
        elif emotions.get("anxiety", 0) > 4:
            suggestions.append("内容可能引起部分观众担忧，建议补充正面信息。")
        else:
            suggestions.append("内容整体可控，但建议注意情绪表达。")

    # 低风险建议
    else:
        if emotions.get("joy", 0) > 5:
            suggestions.append("内容积极向上，建议保持这类创作方向。")
        elif emotions.get("calm", 0) > 5:
            suggestions.append("内容理性客观，传播正能量。")
        else:
            suggestions.append("内容情绪平衡，可正常发布。")

    return " ".join(suggestions)


# ============================================
# 工具函数
# ============================================

def check_dependencies() -> Dict[str, bool]:
    """检查各依赖是否可用"""
    return {
        "torch": True,
        "torchvision": TORCHVISION_AVAILABLE,
        "transformers": TRANSFORMERS_AVAILABLE,
        "cv2": CV2_AVAILABLE,
        "librosa": LIBROSA_AVAILABLE,
    }


def get_model_info() -> Dict[str, Any]:
    """获取模型信息"""
    return {
        "device": str(DEVICE),
        "cuda_available": torch.cuda.is_available(),
        "model_path": str(MODEL_PATH),
        "model_exists": MODEL_PATH.exists(),
        "config": MODEL_CONFIG,
    }
