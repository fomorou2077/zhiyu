"""
百炼多模态视频分析服务

使用阿里云百炼的多模态模型（如 qwen-vl-plus）分析视频内容。
对于视频文件，提取第一帧作为图像进行分析。
"""

import os
import json
import random
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings
from app.utils.logger import logger

# 百炼 API 配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# 百炼多模态 API 端点
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


async def extract_first_frame(video_path: str) -> Optional[str]:
    """
    提取视频的第一帧作为图片保存。

    Args:
        video_path: 视频文件路径

    Returns:
        保存的图片路径，或 None（如果提取失败）
    """
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("无法打开视频文件: {}", video_path)
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret:
            logger.warning("无法读取视频帧: {}", video_path)
            return None

        # 保存为临时文件
        frame_path = video_path + ".jpg"
        cv2.imwrite(frame_path, frame)
        logger.info("视频第一帧已保存: {}", frame_path)
        return frame_path

    except ImportError:
        logger.warning("OpenCV 未安装，无法提取视频帧")
        return None
    except Exception as e:
        logger.error("提取视频帧失败: {}", e)
        return None


def _build_multimodal_prompt() -> str:
    """构建多模态分析的提示词"""
    return """请分析这段视频的内容和情绪倾向。

请从以下维度进行分析：
1. 视频内容概述（用一句话描述）
2. 情绪倾向（六维度评分，每项 0-10）：
   - 喜悦(joy): 积极、愉快的情绪
   - 悲伤(sadness): 消极、难过的情绪
   - 愤怒(anger): 激动、愤怒的情绪
   - 平静(calm): 冷静、平和的情绪
   - 焦虑(anxiety): 紧张、担忧的情绪
   - 期待(expectation): 期待、希望的情绪
3. 风险评分（0-100，越高风险越大）
4. 关键词（3-5个，反映内容主题）
5. 内容类别（娱乐/科技/社会/情感/教育/其他）
6. 建议（50字以内的发布建议）

请严格以JSON格式输出，不要包含其他内容：
{
    "content_summary": "视频内容概述",
    "emotions": {"joy": 0-10, "sadness": 0-10, "anger": 0-10, "calm": 0-10, "anxiety": 0-10, "expectation": 0-10},
    "risk_score": 0-100,
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "category": "类别",
    "suggestions": "发布建议"
}"""


async def analyze_with_qwen_vl(image_path: str, video_path: str = "") -> Dict[str, Any]:
    """
    使用百炼 qwen-vl-plus 模型分析图片内容。

    Args:
        image_path: 图片文件路径
        video_path: 原始视频路径（用于记录日志）

    Returns:
        分析结果字典
    """
    import base64

    if not DASHSCOPE_API_KEY:
        logger.warning("未配置 DASHSCOPE_API_KEY，使用模拟数据")
        return _generate_simulation_result(video_path)

    try:
        # 读取图片并进行 base64 编码
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 构造请求
        headers = {
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "qwen-vl-plus",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": _build_multimodal_prompt()
                        }
                    ]
                }
            ],
            "max_tokens": 1000
        }

        # 调用 API
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                DASHSCOPE_API_URL,
                headers=headers,
                json=payload
            )

        if response.status_code != 200:
            logger.error("百炼 API 调用失败: {} - {}", response.status_code, response.text)
            return _generate_simulation_result(video_path)

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        logger.info("百炼多模态分析响应长度: {} 字符", len(content))

        # 解析 JSON 响应
        return _parse_multimodal_response(content, video_path)

    except Exception as e:
        logger.error("百炼多模态分析失败: {}", e)
        return _generate_simulation_result(video_path)


def _parse_multimodal_response(content: str, video_path: str) -> Dict[str, Any]:
    """解析百炼返回的文本内容，提取结构化数据"""
    try:
        # 尝试提取 JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            data = json.loads(json_match.group())

            # 验证并规范化数据
            emotions = data.get("emotions", {})
            emotions = {
                "joy": max(0, min(10, float(emotions.get("joy", 5)))),
                "sadness": max(0, min(10, float(emotions.get("sadness", 3)))),
                "anger": max(0, min(10, float(emotions.get("anger", 2)))),
                "calm": max(0, min(10, float(emotions.get("calm", 5)))),
                "anxiety": max(0, min(10, float(emotions.get("anxiety", 3)))),
                "expectation": max(0, min(10, float(emotions.get("expectation", 4)))),
            }

            risk_score = max(0, min(100, int(data.get("risk_score", 50))))

            keywords = data.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = [str(keywords)]
            keywords = [str(k) for k in keywords[:5]]

            category = data.get("category", "其他")

            # 计算风险分数（如果模型没返回）
            if data.get("risk_score") is None:
                risk_score = _calculate_risk_score(emotions)

            return {
                "emotions": emotions,
                "risk_score": risk_score,
                "keywords": keywords if keywords else ["视频内容"],
                "suggestions": data.get("suggestions", "请根据内容谨慎发布"),
                "category": category,
                "content_summary": data.get("content_summary", ""),
                "mode": "qwen_vl"
            }
    except json.JSONDecodeError:
        logger.warning("无法解析百炼返回的 JSON，使用默认数据")

    # 解析失败，返回模拟数据
    return _generate_simulation_result(video_path)


def _calculate_risk_score(emotions: Dict[str, float]) -> int:
    """基于情绪分数计算风险评分"""
    weights = {
        "joy": -0.5,
        "sadness": 1.0,
        "anger": 1.5,
        "calm": -0.3,
        "anxiety": 1.3,
        "expectation": 0.0,
    }

    score = 50
    for emotion, value in emotions.items():
        score += weights.get(emotion, 0) * value

    return max(0, min(100, int(score)))


def _generate_simulation_result(video_path: str) -> Dict[str, Any]:
    """生成模拟分析结果（当 API 调用失败时使用）"""
    # 基于视频路径生成伪随机但稳定的数据
    seed = hash(video_path) % 1000
    rng = random.Random(seed)

    emotions = {
        "joy": round(rng.uniform(3, 8), 1),
        "sadness": round(rng.uniform(1, 5), 1),
        "anger": round(rng.uniform(1, 4), 1),
        "calm": round(rng.uniform(3, 7), 1),
        "anxiety": round(rng.uniform(2, 6), 1),
        "expectation": round(rng.uniform(3, 8), 1),
    }

    risk_score = _calculate_risk_score(emotions)

    categories = ["娱乐", "科技", "社会", "情感", "教育", "其他"]
    category = rng.choice(categories)

    return {
        "emotions": emotions,
        "risk_score": risk_score,
        "keywords": ["视频内容", "多模态分析", category],
        "suggestions": f"该视频分析结果为{category}类内容，请根据实际情况判断发布。",
        "category": category,
        "content_summary": "视频内容概述",
        "mode": "simulation"
    }


async def analyze_video_multimodal_advanced(video_path: str) -> Dict[str, Any]:
    """
    高级多模态视频分析入口。

    流程：
    1. 提取视频第一帧
    2. 调用百炼 qwen-vl-plus 分析
    3. 解析结果并返回

    Args:
        video_path: 视频文件路径

    Returns:
        分析结果字典
    """
    logger.info("=" * 50)
    logger.info("开始高级多模态视频分析: {}", video_path)

    # 1. 提取第一帧
    frame_path = await extract_first_frame(video_path)

    if frame_path and os.path.exists(frame_path):
        # 2. 调用百炼分析
        result = await analyze_with_qwen_vl(frame_path, video_path)

        # 3. 清理临时文件
        try:
            os.remove(frame_path)
        except:
            pass
    else:
        # 提取失败，使用模拟结果
        logger.warning("无法提取视频帧，使用模拟分析结果")
        result = _generate_simulation_result(video_path)

    logger.info("高级多模态分析完成: risk_score={}, category={}, mode={}",
                result["risk_score"], result.get("category", "其他"), result.get("mode", "unknown"))
    logger.info("=" * 50)

    return result


def check_multimodal_availability() -> Dict[str, Any]:
    """检查多模态分析功能是否可用"""
    has_cv2 = False
    try:
        import cv2
        has_cv2 = True
    except ImportError:
        pass

    has_api_key = bool(DASHSCOPE_API_KEY)

    return {
        "frame_extraction": has_cv2,
        "qwen_vl_api": has_api_key,
        "available": has_cv2 and has_api_key,
        "mode": "advanced" if (has_cv2 and has_api_key) else "simulation"
    }
