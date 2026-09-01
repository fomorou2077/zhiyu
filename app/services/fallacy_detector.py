"""
逻辑谬误识别服务 - Logical Fallacy Detection
基于 LLM 识别文本中的常见逻辑谬误
"""
import json

from app.services.baichuan_service import chat_with_ai

# 常见逻辑谬误类型
FALLACY_TYPES = [
    "人身攻击 (Ad Hominem)",
    "稻草人谬误 (Straw Man)",
    "诉诸情感 (Appeal to Emotion)",
    "虚假两难 (False Dilemma)",
    "滑坡谬误 (Slippery Slope)",
    "循环论证 (Circular Reasoning)",
    "因果谬误 (False Cause)",
    "以偏概全 (Hasty Generalization)",
    "诉诸权威 (Appeal to Authority)",
    "转移话题 (Red Herring)",
    "诉诸无知 (Appeal to Ignorance)",
    "乐队花车 (Bandwagon)",
    "含糊其辞 (Ambiguity)",
    "合成谬误 (Composition)",
    "分解谬误 (Division)",
]


async def detect_fallacies(text: str) -> dict:
    """
    检测文本中的逻辑谬误
    返回: {fallacies_found, overall_assessment}
    """
    fallacy_list = "\n".join(f"- {f}" for f in FALLACY_TYPES)

    prompt = f"""你是一个专业的逻辑分析专家。请分析以下文本中存在的逻辑谬误。

文本：「{text}」

常见逻辑谬误类型（供参考）：
{fallacy_list}

请以 JSON 格式返回分析结果：
{{
  "fallacies_found": [
    {{"name": "谬误名称", "description": "为什么这是谬误", "excerpt": "原文中的相关片段", "severity": "high | medium | low"}}
  ],
  "overall_assessment": "整体评估，包括文本的论证质量和主要问题"
}}

如果未发现逻辑谬误，返回空的 fallacies_found 数组。"""

    try:
        messages = [{"role": "user", "content": prompt}]
        response = await chat_with_ai(messages, model="qwen-plus")
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        return json.loads(response)
    except Exception:
        return {
            "fallacies_found": [],
            "overall_assessment": "AI分析服务暂时不可用，请稍后重试",
        }
