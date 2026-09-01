"""
立场光谱分析服务 - Position Spectrum Analyzer
分析某个话题下各方观点立场，生成可视化光谱
"""
import json

from app.services.baichuan_service import chat_with_ai


async def analyze_spectrum(topic: str) -> dict:
    """
    分析某个话题的立场光谱
    返回: {positions, spectrum_visualization}
    """
    prompt = f"""你是一个舆论分析专家。请分析以下话题的多方立场，生成一个立场光谱。

话题：「{topic}」

请找出该话题下至少5个不同的观点立场，按照从"极左/激进"到"极右/保守"的光谱排列。

请以 JSON 格式返回：
{{
  "positions": [
    {{"source": "代表来源或群体", "stance_label": "立场标签(如：激进改革派)", "position_score": 0.0-1.0（0=最左，1=最右）, "excerpt": "代表性观点摘要"}}
  ],
  "spectrum_visualization": {{
    "labels": ["激进左翼", "中间偏左", "中立", "中间偏右", "保守右翼"],
    "distribution": [0-100, 0-100, 0-100, 0-100, 0-100],
    "hotspots": [{{"label": "争议焦点", "position": 0.0-1.0, "intensity": 0-100}}]
  }}
}}"""

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
            "positions": [],
            "spectrum_visualization": {
                "labels": ["左", "中左", "中", "中右", "右"],
                "distribution": [20, 25, 30, 15, 10],
                "hotspots": [],
            },
        }
