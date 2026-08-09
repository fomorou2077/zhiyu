import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

import vosk

from app.services.baichuan_service import analyze_emotion
from app.utils.logger import logger

# 全局 Vosk 模型单例
_vosk_model: Optional[vosk.Model] = None

# 模型路径
MODEL_PATH = Path("models/vosk-model-cn-0.22")

# 内容分类的风险加权系数
# 高风险标签（政治、社会）：risk_score = min(100, risk_score * 1.5)
# 中风险标签（娱乐、科技）：risk_score = risk_score * 0.9
# 低风险标签（游戏、生活、教育）：risk_score = risk_score * 0.6
# 其他标签：保持原样
CATEGORY_WEIGHTS = {
    "政治": 1.5,
    "社会": 1.5,
    "娱乐": 0.9,
    "科技": 0.9,
    "游戏": 0.6,
    "生活": 0.6,
    "教育": 0.6,
    "其他": 1.0,
}


def _apply_category_weight(risk_score: float, category: str) -> float:
    """
    根据内容分类标签对风险分数进行加权调整。
    
    Args:
        risk_score: 原始风险分数 (0-100)
        category: 内容分类标签
        
    Returns:
        调整后的风险分数 (0-100)，四舍五入取整
    """
    weight = CATEGORY_WEIGHTS.get(category, 1.0)
    adjusted_score = risk_score * weight
    # 确保分数在 0-100 之间
    adjusted_score = min(100, adjusted_score)
    adjusted_score = max(0, adjusted_score)
    # 四舍五入取整
    return round(adjusted_score)


def _get_vosk_model() -> vosk.Model:
    """获取 Vosk 模型单例，按需加载。"""
    global _vosk_model
    if _vosk_model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Vosk 模型未找到: {MODEL_PATH}，请确保模型已解压到正确位置。"
            )
        logger.info("正在加载 Vosk 中文模型...")
        _vosk_model = vosk.Model(str(MODEL_PATH))
        logger.info("Vosk 模型加载完成")
    return _vosk_model


def _check_ffmpeg() -> bool:
    """检查 ffmpeg 是否已安装。"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _extract_audio(video_path: str) -> str:
    """
    使用 ffmpeg 从视频中提取音频。

    返回临时音频文件路径。
    """
    audio_path = video_path + ".wav"
    cmd = [
        "ffmpeg",
        "-y",  # 覆盖输出文件
        "-i", video_path,
        "-acodec", "pcm_s16le",  # PCM 16-bit 小端格式
        "-ar", "16000",  # 16kHz 采样率（Vosk 需要）
        "-ac", "1",  # 单声道
        audio_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return audio_path


def _transcribe_sync(video_path: str) -> str:
    """
    同步执行 Vosk 转写。
    捕获 ffmpeg 缺失和转写失败的错误。
    """
    if not _check_ffmpeg():
        raise FileNotFoundError(
            "ffmpeg 未安装，请使用 winget install ffmpeg 安装。"
        )

    model = _get_vosk_model()

    # 1. 提取音频
    logger.info("从视频提取音频: {}", video_path)
    audio_path = _extract_audio(video_path)

    try:
        # 2. 使用 Vosk 进行转写
        logger.info("开始 Vosk 转写...")
        with open(audio_path, "rb") as f:
            recognizer = vosk.KaldiRecognizer(model, 16000)
            text_parts = []

            while True:
                data = f.read(4000)
                if not data:
                    break
                if recognizer.AcceptWaveform(data):
                    result = recognizer.Result()
                    text_parts.append(result)

            # 获取最终结果
            final_result = recognizer.FinalResult()
            text_parts.append(final_result)

        # 3. 解析 Vosk JSON 输出
        # Vosk 每次 AcceptWaveform 会返回 {"result": [...], "text": "..."}
        # FinalResult 同理。取 "text" 字段拼接即可。
        full_text = ""
        for part in text_parts:
            try:
                import json
                parsed = json.loads(part)
                segment = parsed.get("text", "")
                if segment:
                    full_text += segment + " "
            except (json.JSONDecodeError, TypeError):
                logger.warning("无法解析 Vosk 输出片段: {}", part[:100])

        full_text = full_text.strip()
        logger.info("Vosk 转写完成，文本长度: {}, 内容预览: {}", len(full_text), full_text[:100])
        return full_text

    finally:
        # 4. 清理临时音频文件
        if os.path.exists(audio_path):
            os.remove(audio_path)


async def extract_video_text(video_path: str) -> str:
    """
    从视频中提取语音并转写为文字。

    使用 asyncio.run_in_executor 包装 Vosk 的同步调用，避免阻塞事件循环。
    - 若 ffmpeg 未安装，抛出 FileNotFoundError。
    - 若模型未找到，抛出 FileNotFoundError。
    - 若转写失败，返回空字符串并记录错误。
    """
    try:
        # Python 3.8 兼容：使用 run_in_executor 替代 to_thread
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _transcribe_sync, video_path)
        return text
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.exception("Vosk 转写失败: {}", e)
        return ""


async def analyze_video_emotion(video_path: str) -> dict:
    """
    根据视频路径提取文本，并调用情绪分析。

    - 若文本为空或过短（< 10 字符），返回友好提示。
    - 捕获转写相关错误，返回不影响接口整体可用性的结果。
    - 根据内容分类标签应用风险加权：
        - 高风险标签（政治、社会）：risk_score = min(100, risk_score * 1.5)
        - 中风险标签（娱乐、科技）：risk_score = risk_score * 0.9
        - 低风险标签（游戏、生活、教育）：risk_score = risk_score * 0.6
        - 其他标签：保持原样
    """
    # 默认返回结果模板（包含 category）
    def _default_result(error_msg: str) -> dict:
        return {
            "emotions": {
                "joy": 0.0,
                "sadness": 0.0,
                "anger": 0.0,
                "calm": 0.0,
                "anxiety": 0.0,
                "expectation": 0.0,
            },
            "risk_score": 0.0,
            "adjusted_risk_score": 0.0,
            "keywords": [],
            "suggestions": f"视频分析失败：{error_msg}",
            "category": "其他",
        }

    try:
        video_text = await extract_video_text(video_path)
    except FileNotFoundError as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg:
            return _default_result(error_msg)
        else:
            return _default_result(error_msg)

    if not video_text or len(video_text) < 10:
        logger.warning("视频未检测到有效语音内容: {}", video_path)
        return {
            "emotions": {
                "joy": 0.0,
                "sadness": 0.0,
                "anger": 0.0,
                "calm": 0.0,
                "anxiety": 0.0,
                "expectation": 0.0,
            },
            "risk_score": 0.0,
            "adjusted_risk_score": 0.0,
            "keywords": [],
            "suggestions": "视频未检测到有效语音内容，请检查视频是否有声音或尝试其他视频。",
            "category": "其他",
        }

    # 调用百炼情绪分析
    result = await analyze_emotion(video_text)
    
    # 获取原始风险分数和分类标签
    original_risk_score = result.get("risk_score", 50.0)
    category = result.get("category", "其他")
    
    # 应用分类加权
    adjusted_risk_score = _apply_category_weight(original_risk_score, category)
    
    # 记录详细日志
    logger.info(
        "情绪分析加权计算: video_path={}, category={}, original_risk_score={}, adjusted_risk_score={}",
        video_path, category, original_risk_score, adjusted_risk_score
    )
    
    # 在返回结果中添加调整后的风险分数和原始分数
    result["original_risk_score"] = original_risk_score
    result["adjusted_risk_score"] = adjusted_risk_score
    # 使用调整后的分数作为主要 risk_score（用于数据库存储）
    result["risk_score"] = adjusted_risk_score
    
    return result


async def analyze_comments(comments: list) -> dict:
    """
    批量分析评论，返回聚合情绪和风险分数
    
    将多条评论合并后进行分析，适用于已发布视频的评论监测。
    
    Args:
        comments: 评论列表
        
    Returns:
        dict: 包含情绪分布、风险评分、关键词和建议
    """
    if not comments:
        return {
            "emotions": {"joy": 0, "sadness": 0, "anger": 0, "calm": 0, "anxiety": 0, "expectation": 0},
            "risk_score": 0,
            "keywords": [],
            "suggestions": "暂无评论",
            "category": "其他"
        }
    
    # 合并评论（最多50条，避免超长）
    combined_text = " ".join(comments[:50])
    
    # 调用现有的情绪分析函数
    result = await analyze_emotion(combined_text)
    
    # 确保返回完整的结果
    return {
        "emotions": result.get("emotions", {
            "joy": 0, "sadness": 0, "anger": 0, "calm": 0, "anxiety": 0, "expectation": 0
        }),
        "risk_score": int(result.get("risk_score", 0)),
        "keywords": result.get("keywords", []),
        "suggestions": result.get("suggestions", ""),
        "category": result.get("category", "其他"),
        "comment_count": len(comments)
    }
