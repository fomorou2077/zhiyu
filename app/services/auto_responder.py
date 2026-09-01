"""
自动回应生成服务 - Auto Response Generator
根据舆情事件类型生成5种企业回应模板
"""
import json

from app.services.baichuan_service import chat_with_ai

RESPONSE_TYPES = {
    "official_statement": "官方声明（正式公告，适合官网/媒体发布）",
    "media_talking_points": "媒体口径（内部FAQ，统一对外口径）",
    "internal_alignment": "内部对齐（全员通告，确保信息一致）",
    "kol_outreach": "KOL沟通（与关键意见领袖的沟通话术）",
    "legal_notice": "法律声明（律师函/法律告知，严肃正式）",
}


async def generate_response(
    incident_description: str,
    brand_name: str = "我司",
    response_type: str = "official_statement",
    incident_severity: str = "medium",
    key_facts: list = None,
) -> dict:
    """
    根据事件描述生成企业回应
    Args:
        incident_description: 事件描述
        brand_name: 品牌名称
        response_type: 回应类型 (official_statement|media_talking_points|internal_alignment|kol_outreach|legal_notice)
        incident_severity: 事件严重程度 (low|medium|high|critical)
        key_facts: 关键事实列表
    Returns:
        {title, content, key_messages, notes}
    """
    type_desc = RESPONSE_TYPES.get(response_type, RESPONSE_TYPES["official_statement"])

    severity_guidance = {
        "low": "事件影响较小，语气可适度轻松，但需表明重视态度",
        "medium": "事件有一定影响，需正式回应，展示积极处理姿态",
        "high": "事件影响较大，需郑重回应，展示具体整改措施和诚意",
        "critical": "危机级别事件，需最高级别回应，展示全面调查和彻底整改决心",
    }
    severity_note = severity_guidance.get(incident_severity, severity_guidance["medium"])

    facts_text = ""
    if key_facts:
        facts_text = "已知关键事实：\n" + "\n".join(f"- {f}" for f in key_facts)

    prompt = f"""你是一位资深的企业公关顾问，现在需要帮助{brand_name}起草一份舆情回应。

事件描述：「{incident_description}」
回应类型：{type_desc}
严重程度：{severity_note}
{facts_text}

请按以下JSON格式生成回应内容：
{{
  "title": "回应标题（简洁有力）",
  "content": "回应正文（根据回应类型调整长度和语气。官方声明约300-500字，KOL沟通约150-200字，法律声明约200-300字）",
  "key_messages": ["核心信息点1", "核心信息点2", "核心信息点3"],
  "tone": "语气描述（如：诚恳致歉、据理力争、温和解释…）",
  "dos_and_donts": ["建议做法1", "建议做法2", "避免事项1"],
  "suggested_channels": ["建议发布渠道1", "建议发布渠道2"]
}}

注意：
1. 回应内容要符合中国互联网舆论环境和监管要求
2. 态度要真诚，避免官腔和套话
3. 官方声明要有事实依据，不回避问题
4. KOL沟通要有人情味，用对方习惯的语言风格
5. 法律声明要严谨，引用的法律条文需准确"""

    try:
        messages = [{"role": "user", "content": prompt}]
        response = await chat_with_ai(messages, model="qwen-plus")
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
        result["response_type"] = response_type
        result["generated_for"] = brand_name
        return result
    except Exception:
        return {
            "title": f"关于近期事件的{'官方声明' if response_type == 'official_statement' else '回应'}",
            "content": f"我们注意到了相关讨论。{brand_name}一直高度重视用户的反馈和关切。我们正在积极核实相关情况，并将及时公布进展。感谢大家的关注与支持。",
            "key_messages": ["我们重视每一条反馈", "正在积极核实情况", "将及时公布进展"],
            "tone": "诚恳、积极",
            "dos_and_donts": ["及时回应关切", "保持信息透明", "避免情绪化回应"],
            "suggested_channels": ["官方微博", "官方微信公众号", "官网公告"],
            "response_type": response_type,
            "generated_for": brand_name,
        }


async def generate_all_responses(
    incident_description: str,
    brand_name: str = "我司",
    incident_severity: str = "medium",
    key_facts: list = None,
) -> dict:
    """为同一事件生成全部5种回应类型"""
    results = {}
    for resp_type in RESPONSE_TYPES:
        results[resp_type] = await generate_response(
            incident_description=incident_description,
            brand_name=brand_name,
            response_type=resp_type,
            incident_severity=incident_severity,
            key_facts=key_facts,
        )
    return {
        "incident": incident_description,
        "brand": brand_name,
        "responses": results,
    }
