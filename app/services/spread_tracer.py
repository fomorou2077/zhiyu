"""
传播路径追踪服务 - Spread Tracer
分析舆情事件的传播路径，生成网络图数据
优先使用 LLM 推理，不可用时降级为模拟数据
"""
import json
import random

from app.services.baichuan_service import chat_with_ai
from app.utils.logger import logger


async def _llm_trace_spread(incident_name: str) -> dict:
    """使用 LLM 推理传播路径"""
    prompt = f"""你是资深舆情分析师。请分析以下事件的传播路径。

事件：「{incident_name}」

请以 JSON 格式返回传播网络数据：
{{
  "nodes": [
    {{"id": "n0", "name": "首发来源（具体平台+账号类型）", "platform": "平台名", "type": "origin", "symbolSize": 50-70, "influence": 0-100, "time": "0h", "reach": 预估触达量}},
    {{"id": "n1", "name": "关键传播节点", "platform": "平台名", "type": "amplifier|hub|leaf", "symbolSize": 10-50, "influence": 0-100, "time": "Nh", "reach": 预估触达量}}
  ],
  "edges": [
    {{"source": "n0", "target": "n1", "weight": 1-10, "label": "转发|扩散|评论|引用"}}
  ],
  "stats": {{
    "total_reach": 预估总触达量,
    "platform_count": 涉及平台数,
    "peak_time": "峰值时间",
    "estimated_duration": "预计持续时长"
  }},
  "pattern_analysis": {{
    "detected_pattern": "传播模式名",
    "description": "模式描述",
    "risk_level": "low|medium|high|critical",
    "suggested_actions": ["建议1", "建议2", "建议3"]
  }}
}}

要求：
1. 根据事件性质推理合理传播路径（如品牌危机→微博首发→大V转发→抖音发酵→知乎深度讨论）
2. 节点数量控制在10-20个
3. 边数量控制在15-30条
4. 传播时间线要合理（0h首发 → 1-2h扩散 → 4-8h峰值 → 24-72h消退）
5. 只返回JSON，不要其他内容"""

    try:
        messages = [{"role": "user", "content": prompt}]
        response = await chat_with_ai(messages, model="qwen-plus")
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
        result["incident_name"] = incident_name
        result["ai_generated"] = True
        logger.info("LLM传播路径分析完成: {}", incident_name)
        return result
    except Exception as e:
        logger.warning("LLM传播路径分析失败，降级为模拟数据: {}", e)
        raise


def _fallback_spread_data(incident_name: str) -> dict:
    """降级方案：随机生成模拟数据"""
    platforms = ["微博", "抖音", "小红书", "B站", "知乎", "微信公众号", "今日头条", "快手"]
    nodes = []
    source_platform = random.choice(["微博", "抖音", "小红书"])
    nodes.append({
        "id": "n0", "name": f"{source_platform}首发", "platform": source_platform,
        "type": "origin", "symbolSize": 60, "influence": random.randint(80, 100),
        "time": "0h", "reach": random.randint(100000, 500000),
    })
    amp_count = random.randint(3, 5)
    for i in range(amp_count):
        plat = random.choice(platforms)
        nodes.append({
            "id": f"n{i+1}", "name": f"{random.choice(['媒体账号','头部KOL','行业大V','官方媒体','自媒体'])}{i+1}",
            "platform": plat, "type": "amplifier", "symbolSize": random.randint(30, 50),
            "influence": random.randint(50, 80), "time": f"{random.randint(1,8)}h",
            "reach": random.randint(10000, 100000),
        })
    hub_count = random.randint(4, 7)
    for i in range(hub_count):
        plat = random.choice(platforms)
        nodes.append({
            "id": f"n{amp_count+1+i}", "name": f"{random.choice(['讨论区','话题主持人','社群群主','论坛版主'])}{i+1}",
            "platform": plat, "type": "hub", "symbolSize": random.randint(20, 35),
            "influence": random.randint(20, 50), "time": f"{random.randint(2,24)}h",
            "reach": random.randint(1000, 10000),
        })
    leaf_count = random.randint(8, 15)
    for i in range(leaf_count):
        plat = random.choice(platforms)
        nodes.append({
            "id": f"n{amp_count+hub_count+1+i}", "name": f"{random.choice(['网友','普通用户','转发用户','评论用户'])}{i+1}",
            "platform": plat, "type": "leaf", "symbolSize": random.randint(8, 15),
            "influence": random.randint(1, 10), "time": f"{random.randint(1,48)}h",
            "reach": random.randint(10, 500),
        })

    edges = []
    for n in nodes:
        if n["type"] == "amplifier":
            edges.append({"source": "n0", "target": n["id"], "weight": random.randint(3, 10), "label": "转发"})
    amplifiers = [n for n in nodes if n["type"] == "amplifier"]
    hubs = [n for n in nodes if n["type"] == "hub"]
    for amp in amplifiers:
        for hub in random.sample(hubs, min(2, len(hubs))):
            edges.append({"source": amp["id"], "target": hub["id"], "weight": random.randint(1, 5), "label": "扩散"})
    leaves = [n for n in nodes if n["type"] == "leaf"]
    for hub in hubs:
        for leaf in random.sample(leaves, min(3, len(leaves))):
            edges.append({"source": hub["id"], "target": leaf["id"], "weight": random.randint(1, 3), "label": "传播"})
    for _ in range(random.randint(3, 6)):
        src = random.choice([n for n in nodes if n["type"] in ("amplifier", "origin")])
        tgt = random.choice([n for n in nodes if n["type"] in ("hub", "leaf") and n["id"] != src["id"]])
        edges.append({"source": src["id"], "target": tgt["id"], "weight": random.randint(1, 2), "label": "跨平台"})

    patterns = [
        {"name": "病毒式扩散", "description": "短时间内大量用户自发传播，节点多而分散", "risk_level": "high"},
        {"name": "KOL驱动", "description": "由少数意见领袖主导，传播路径集中", "risk_level": "medium"},
        {"name": "媒体引爆", "description": "传统媒体首发后社交媒体跟进，多轮次传播", "risk_level": "high"},
        {"name": "社群发酵", "description": "在封闭社群中酝酿后外溢到公开平台", "risk_level": "medium"},
        {"name": "跨平台联动", "description": "多个平台同时讨论，互相引用形成共振", "risk_level": "critical"},
    ]
    pattern = random.choice(patterns)

    return {
        "incident_name": incident_name,
        "nodes": nodes, "edges": edges,
        "stats": {
            "total_reach": sum(n["reach"] for n in nodes),
            "platform_count": len(set(n["platform"] for n in nodes)),
            "node_count": len(nodes), "edge_count": len(edges),
            "peak_time": f"{random.randint(3,12)}h",
            "estimated_duration": f"{random.randint(24,72)}h",
        },
        "pattern_analysis": {
            "detected_pattern": pattern["name"],
            "description": pattern["description"],
            "risk_level": pattern["risk_level"],
            "key_nodes": random.randint(3, 8),
            "peak_platforms": random.sample(["微博","抖音","小红书","B站","知乎"], k=random.randint(2,4)),
            "suggested_actions": [
                "密切关注核心传播节点的后续动态",
                "在主要传播平台建立官方回应渠道",
                "准备多版本回应口径以应对不同平台语境",
            ],
        },
        "ai_generated": False,
    }


async def trace_spread(incident_id: int, incident_keywords: list = None) -> dict:
    """追踪事件传播路径。优先 LLM 推理，失败时降级为模拟数据"""
    keywords = incident_keywords or ["舆情事件"]
    incident_name = "、".join(keywords[:3])

    try:
        return await _llm_trace_spread(incident_name)
    except Exception:
        return _fallback_spread_data(incident_name)


async def analyze_spread_pattern(incident_id: int) -> dict:
    """分析传播模式特征（已整合进 trace_spread 的 pattern_analysis 中）"""
    return {
        "note": "传播模式分析已整合到 trace_spread 返回结果中",
        "incident_id": incident_id,
    }
