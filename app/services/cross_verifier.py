"""
多语言信源交叉验证服务 - Cross-Verification
对同一主张在不同语言的信息源中进行交叉比对
"""
import json

from app.services.baichuan_service import chat_with_ai


async def cross_verify_claim(claim: str, languages: list) -> dict:
    """
    对一条主张进行多语言信源交叉验证
    返回: {sources_by_language, consensus_level}
    """
    lang_names = {
        "zh": "中文",
        "en": "英文",
        "ja": "日文",
        "ko": "韩文",
        "fr": "法文",
        "de": "德文",
        "es": "西班牙文",
        "ru": "俄文",
    }
    lang_list = ", ".join(lang_names.get(l, l) for l in languages)

    prompt = f"""你是一个多语言信息核查专家。请在{lang_list}等不同语言的信息源中，对以下主张进行交叉验证。

主张：「{claim}」

请评估这条主张在跨语言、跨文化信息源中的一致性。

请以 JSON 格式返回：
{{
  "sources_by_language": {{
    "zh": [{{"source": "来源名", "snippet": "信息片段", "stance": "support | oppose | neutral"}}],
    "en": [...]
  }},
  "consensus_level": "broad_consensus | mixed | mostly_contradicts | no_data",
  "summary": "交叉验证的总结"
}}

注意：由于Demo模式下无法真实联网搜索，请基于模型知识给出合理推演。"""

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
            "sources_by_language": {l: [] for l in languages},
            "consensus_level": "no_data",
            "summary": "交叉验证服务暂时不可用",
        }
