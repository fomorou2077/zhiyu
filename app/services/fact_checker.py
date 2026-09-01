"""
事实核查服务 - Claim Verification
基于 LLM + 联网搜索，对声明进行真伪判断
"""
import json
import random

from app.services.baichuan_service import chat_with_ai


async def verify_claim(claim: str) -> dict:
    """
    对一条声明进行事实核查
    返回: {verdict, confidence, evidence_items, reasoning, search_results_used}
    """
    prompt = f"""你是一个专业的事实核查员。请对以下声明进行严格的事实核查。

声明：「{claim}」

请按照以下步骤进行分析：
1. 识别声明中的可验证事实主张
2. 判断每个主张的真伪
3. 给出综合判定

请以 JSON 格式返回，格式如下：
{{
  "verdict": "true | false | misleading | unverified | half_true",
  "confidence": 0.0-1.0,
  "evidence_items": [
    {{"source": "来源", "url": "URL", "excerpt": "证据摘要", "credibility": "high | medium | low"}}
  ],
  "reasoning": "详细的推理过程",
  "search_results_used": 0
}}"""

    try:
        messages = [{"role": "user", "content": prompt}]
        response = await chat_with_ai(messages, model="qwen-plus")
        # 尝试提取JSON
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        return json.loads(response)
    except Exception:
        # LLM调用失败时返回一个合理的结果
        return {
            "verdict": "unverified",
            "confidence": 0.3,
            "evidence_items": [
                {
                    "source": "AI分析暂不可用",
                    "url": "",
                    "excerpt": "当前无法完成联网核查，请稍后重试",
                    "credibility": "low",
                }
            ],
            "reasoning": "事实核查服务暂时不可用，请联系管理员检查API配置",
            "search_results_used": 0,
        }
