import json
import re
from typing import Any, Dict, List

import dashscope

from app.config import settings
from app.utils.logger import logger

dashscope.api_key = settings.dashscope_api_key

# ============================================
# 风险分析常量配置
# ============================================

# 内容分类标签的可选值
CONTENT_CATEGORIES = ["政治", "社会", "娱乐", "游戏", "科技", "生活", "教育", "其他"]

# 领域风险系数（可配置）
DOMAIN_RISK_COEFFICIENTS = {
    "政治": 1.5,   # 政治类：风险加成50%
    "社会": 1.5,   # 社会类：风险加成50%
    "娱乐": 0.9,   # 娱乐类：风险轻微加成
    "游戏": 0.6,   # 游戏类：风险降权40%
    "科技": 0.9,   # 科技类：风险轻微加成
    "生活": 0.6,   # 生活类：风险降权40%
    "教育": 0.6,   # 教育类：风险降权40%
    "其他": 1.0,   # 其他类：基准系数
}

# 情绪权重配置（用于计算加权平均）
EMOTION_WEIGHTS = {
    "anger": 1.5,    # 愤怒权重更高
    "anxiety": 1.3,  # 焦虑权重较高
    "sadness": 1.0,  # 悲伤基准
    "joy": 0.5,      # 喜悦降低风险
    "calm": 0.5,     # 平静降低风险
    "expectation": 0.3,  # 期待轻微正向
}


def _build_crispe_prompt(text: str) -> str:
    """
    构建基于CRISPE框架的结构化提示词
    """
    return f"""# CRISPE Prompt Framework

## Capacity and Role (角色与能力)
你是一位顶尖的视频内容风控专家，拥有10年社交媒体舆情分析经验。你擅长：
- 精准识别视频内容的领域类别
- 多维度情绪量化分析（6维度0-10分）
- 基于领域风险权重的内容风险评估
- 区分"情绪激烈"与"真正危险"的内容

## Insight (核心洞察)
**重要认知**：
- 游戏解说视频即使情绪激动（愤怒8分、焦虑7分），只要内容不涉及政治、社会敏感话题，**实际风险远低于**一个情绪平和（愤怒3分）但谈论政治的视频
- 你的核心任务不是"检测情绪强度"，而是"判断内容是否真的危险"
- 风险公式 = 加权情绪分 × 领域风险系数
  - 政治/社会类：风险系数 ×1.5
  - 娱乐/科技类：风险系数 ×0.9
  - 游戏/生活/教育类：风险系数 ×0.6
  - 其他类：风险系数 ×1.0

## Statement (任务要求)
请对用户提供的文本执行**三步推理**：

### 第一步：领域识别
分析文本属于以下哪个领域（必须选择一项）：
- 政治：涉及政府、政策、领导人、国际关系
- 社会：涉及民生、道德、公共事件、法律争议
- 娱乐：明星、综艺、影视、音乐
- 游戏：游戏解说、攻略、电竞、直播
- 科技：数码产品、技术评测、AI
- 生活：Vlog、美食、旅行、日常
- 教育：知识科普、教学、课程
- 其他：无法归类的

**输出格式**：`[领域识别] 领域名称`

### 第二步：情绪分析
分析文本的6维度情绪分数（0-10）：
- joy：喜悦（积极、开心、满意）
- sadness：悲伤（失望、难过、遗憾）
- anger：愤怒（激动、不满、批判）
- calm：平静（冷静、客观、理性）
- anxiety：焦虑（担忧、紧张、不安）
- expectation：期待（好奇、向往、渴望）

**输出格式**：`[情绪分数] {{"joy":X, "sadness":X, "anger":X, "calm":X, "anxiety":X, "expectation":X}}`

### 第三步：风险评估
基于领域和情绪计算最终风险：
1. 先根据领域确定风险系数
2. 计算加权平均情绪分（愤怒、焦虑权重更高）
3. 风险分数 = 加权平均情绪分 × 风险系数，范围0-100
4. 风险等级：0-40低风险，41-70中风险，71-100高风险
5. 提取3-5个关键词
6. 生成针对性建议

**输出格式**：`[风险评估] {{"risk_score":X, "keywords":["A","B"], "suggestions":"建议内容"}}`

## Person (输出风格)
- 严格按JSON格式输出最终结果
- 推理过程用[领域识别]、[情绪分数]、[风险评估]标签标注
- 最终输出为单一JSON对象，包含所有字段

## Experiment (示例参考)

### 示例1：游戏视频（低风险）
**输入文本**："这波操作太帅了！对面完全被打懵了，兄弟们快来看我秀翻全场！"
**正确输出**：
[领域识别] 游戏
[情绪分数] {{"joy":8,"sadness":1,"anger":2,"calm":2,"anxiety":1,"expectation":9}}
[风险评估] 游戏领域(系数0.6) × 情绪分 → 最终风险约14分
{{"category":"游戏","emotions":{{"joy":8,"sadness":1,"anger":2,"calm":2,"anxiety":1,"expectation":9}},"risk_score":14,"keywords":["游戏解说","操作精彩","娱乐性强"],"suggestions":"内容积极健康，适合所有年龄段，建议增加互动环节提升粉丝粘性。"}}

### 示例2：政治评论（高风险）
**输入文本**："这个政策明显不合理，老百姓根本承受不了，政府完全不了解实际情况"
**正确输出**：
[领域识别] 政治
[情绪分数] {{"joy":0,"sadness":6,"anger":8,"calm":1,"anxiety":7,"expectation":0}}
[风险评估] 政治领域(系数1.5) × 情绪分 → 最终风险约93分
{{"category":"政治","emotions":{{"joy":0,"sadness":6,"anger":8,"calm":1,"anxiety":7,"expectation":0}},"risk_score":93,"keywords":["政策质疑","政府批评","民生问题"],"suggestions":"内容涉及敏感政策讨论，情绪偏向负面。建议：1）若为新闻评论，需确保事实准确；2）避免绝对化表述；3）可补充建设性意见平衡观点。"}}

### 示例3：游戏情绪激动但无害（中风险误解）
**输入文本**："这个游戏太垃圾了，策划脑子进水了吗？气得我想砸电脑！"
**正确输出**：
[领域识别] 游戏
[情绪分数] {{"joy":0,"sadness":4,"anger":9,"calm":0,"anxiety":3,"expectation":0}}
[风险评估] 游戏领域(系数0.6) × 情绪分 → 最终风险约29分
{{"category":"游戏","emotions":{{"joy":0,"sadness":4,"anger":9,"calm":0,"anxiety":3,"expectation":0}},"risk_score":29,"keywords":["游戏吐槽","情绪宣泄"],"suggestions":"内容为游戏吐槽，虽情绪激动但领域安全。建议：避免使用人身攻击词汇，可用'设计不够合理'等中性表达。"}}

## Input Data (待分析文本)
{text}

## Output Format
请严格按以下JSON格式输出最终结果（只输出JSON，不要其他内容）：
{{
    "category": "领域名称",
    "emotions": {{"joy":0-10,"sadness":0-10,"anger":0-10,"calm":0-10,"anxiety":0-10,"expectation":0-10}},
    "risk_score": 0-100,
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "suggestions": "建议文本"
}}"""


async def analyze_emotion(text: str) -> Dict[str, Any]:
    """
    使用CRISPE框架 + 思维链分解的情绪分析函数。

    - 分阶段推理：领域识别 → 情绪分析 → 风险评估
    - 基于领域风险系数的加权风险计算
    - 若调用失败或结果无法解析，返回带有默认值的结果
    """

    def _default_result() -> Dict[str, Any]:
        return {
            "emotions": {
                "joy": 5.0,
                "sadness": 5.0,
                "anger": 5.0,
                "calm": 5.0,
                "anxiety": 5.0,
                "expectation": 5.0,
            },
            "risk_score": 50.0,
            "keywords": ["示例"],
            "suggestions": "暂无分析结果，请稍后重试",
            "category": "其他",
        }

    def _parse_and_validate_result(content: str, original_text: str) -> Dict[str, Any]:
        """
        解析API响应并验证/修正结果
        """
        # 提取JSON部分（响应中会包含带标签的推理过程和最后的JSON）
        json_patterns = [
            r'\{\s*"category"[^}]+\}',
            r'\{\s*"emotions"[^}]+\}',
            r'\{[^{}]*"joy"[^{}]*"risk_score"[^{}]*\}',
        ]

        result = None
        for pattern in json_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                    break
                except json.JSONDecodeError:
                    continue

        if not result:
            # 尝试直接解析整个content
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("无法从响应中提取JSON: {}", content[:200])
                return _default_result()

        # 验证和补全字段
        emotions = result.get("emotions") or {}
        for k in ["joy", "sadness", "anger", "calm", "anxiety", "expectation"]:
            emotions.setdefault(k, 5.0)
            # 确保值在0-10范围内
            try:
                emotions[k] = max(0, min(10, float(emotions[k])))
            except (ValueError, TypeError):
                emotions[k] = 5.0
        result["emotions"] = emotions

        # 验证category
        category = result.get("category", "其他")
        if category not in CONTENT_CATEGORIES:
            category = "其他"
        result["category"] = category

        # 验证风险分数
        risk_score = result.get("risk_score", 50.0)
        try:
            risk_score = max(0, min(100, float(risk_score)))
        except (ValueError, TypeError):
            risk_score = 50.0

        # 应用领域风险系数修正（如果模型没有正确应用）
        domain = result.get("category", "其他")
        coefficient = DOMAIN_RISK_COEFFICIENTS.get(domain, 1.0)

        # 如果模型没有应用领域系数，我们重新计算
        # 这里做个简单判断：如果风险分明显不合理（比如游戏类但风险>50）
        if domain in ["游戏", "生活", "教育"] and risk_score > 50:
            # 重新计算加权情绪分
            weighted_sum = 0
            weight_sum = 0
            for emo, weight in EMOTION_WEIGHTS.items():
                val = emotions.get(emo, 5.0)
                weighted_sum += val * weight
                weight_sum += weight
            avg_emotion = weighted_sum / weight_sum if weight_sum > 0 else 5.0
            risk_score = min(100, avg_emotion * coefficient * 10)
            logger.info("应用领域系数修正: domain={}, coefficient={}, original_risk={}, new_risk={}",
                       domain, coefficient, result.get("risk_score"), risk_score)

        result["risk_score"] = round(risk_score, 1)
        result.setdefault("keywords", [])
        result.setdefault("suggestions", "暂无建议")

        # 记录分析结果
        logger.info("情绪分析完成: category={}, risk_score={}", result["category"], result["risk_score"])

        return result

    # 构建CRISPE提示词
    prompt = _build_crispe_prompt(text)
    logger.debug("发送情绪分析请求: text={}", text[:100])

    last_error: Exception | None = None
    for attempt in range(2):  # 简单重试最多2次
        try:
            response = dashscope.Generation.call(
                model="qwen-max",
                messages=[{"role": "user", "content": prompt}],
                result_format="message",
            )

            if response.status_code != 200:
                logger.error("百炼API错误(status_code={}): {}", response.status_code, response)
                last_error = RuntimeError(f"bad status code: {response.status_code}")
                continue

            content = response.output.choices[0].message.content
            logger.debug("百炼API响应: {}", content[:500])

            result = _parse_and_validate_result(content, text)
            return result

        except Exception as e:
            last_error = e
            logger.exception("调用百炼情绪分析失败(第 {} 次): {}", attempt + 1, e)

    logger.error("情绪分析全部重试失败，将返回默认结果: {}", last_error)
    return _default_result()


async def chat_with_ai(
    messages: List[Dict[str, str]],
    enable_search: bool = False,
    model: str = "qwen-turbo"
) -> str:
    """
    与百炼大模型对话

    Args:
        messages: 对话消息列表
        enable_search: 是否开启联网搜索（仅 qwen-max 等模型支持）
        model: 使用的模型名称

    Returns:
        模型回复文本
    """
    try:
        # 构建调用参数
        call_params = {
            "model": model,
            "messages": messages,
            "result_format": "message",
        }

        # 如果开启联网搜索且使用支持搜索的模型
        if enable_search and model in ["qwen-max", "qwen-plus"]:
            call_params["enable_search"] = True

        response = dashscope.Generation.call(**call_params)

        if response.status_code == 200:
            return response.output.choices[0].message.content
        logger.error("对话API错误: {}", response)
        return "抱歉，我现在无法回答，请稍后再试。"
    except Exception as e:
        logger.exception(e)
        return "出现了一些问题，请稍后再试。"


async def generate_care_message(username: str, care_type: str, recent_records: List[Dict[str, Any]]) -> str:
    """
    生成关怀消息。
    """
    prompt = f"""你是一位温暖的AI助手"知知"，正在关怀用户 {username}。

关怀类型：{care_type}

用户最近的分析记录：
{json.dumps(recent_records, ensure_ascii=False, indent=2)}

请生成一段温馨的关怀话语（100字以内），用"知知"的口吻，表达关心和鼓励。不要使用任何特殊格式，直接输出关怀内容即可。"""
    
    messages = [{"role": "user", "content": prompt}]
    return await chat_with_ai(messages, enable_search=False)


async def generate_tailored_suggestions(
    risk_score: float,
    emotions: Dict[str, float],
    keywords: List[str],
    category: str = "其他"
) -> Dict[str, str]:
    """
    根据风险分数、情绪数据等生成分层建议。

    返回格式：{
        "title": "建议标题",
        "content": "具体建议文本",
        "encouragement": "鼓励语"
    }
    """
    # 确保关键词列表有效
    if not keywords:
        keywords = ["内容创作"]
    display_keywords = keywords[:3] if len(keywords) >= 3 else keywords

    # 找出主导情绪
    dominant_emotion = "中性"
    if emotions:
        max_val = -1
        emotion_names = {
            "joy": "喜悦",
            "sadness": "悲伤",
            "anger": "愤怒",
            "calm": "平静",
            "anxiety": "焦虑",
            "expectation": "期待"
        }
        for key, name in emotion_names.items():
            val = emotions.get(key, 0)
            if val > max_val:
                max_val = val
                dominant_emotion = name

    # 根据风险等级生成建议
    if risk_score < 40:
        # 低风险
        title = "✨ 视频表现优秀！"
        content = (
            "你的视频风险很低，内容安全。为了进一步提升吸引力，可以尝试：\n\n"
            "1. 在开头3秒设置悬念或高能片段\n"
            "2. 使用热门话题标签增加曝光\n"
            "3. 与粉丝互动，设计提问结尾\n"
            "4. 优化封面图和标题关键词\n"
            "5. 保持更新频率，培养粉丝习惯"
        )
        encouragement = "继续保持创作热情，你的内容很有潜力！"

    elif risk_score < 70:
        # 中风险
        title = "⚠️ 存在一定风险，建议调整"
        content = (
            f"视频中可能存在以下风险点：\n"
            f"- 关键词：{', '.join(display_keywords)}\n"
            f"- 情绪偏向：{dominant_emotion} 偏高\n"
            f"- 领域分类：{category}\n\n"
            "建议修改方案：\n"
            "• 将激烈用词改为中性表述\n"
            "• 增加解释性内容，避免观众误解\n"
            "• 添加正向引导，强调观点仅为个人感受\n"
            "• 如涉及争议话题，可添加免责声明"
        )
        encouragement = "及时调整能让内容更安全，也更容易获得观众认可。"

    else:
        # 高风险
        title = "🚨 高风险预警！请谨慎处理"
        content = (
            f"视频内容可能引发争议，主要风险点：\n"
            f"- {', '.join(display_keywords)}\n"
            f"- 负面情绪（{dominant_emotion}）强度较高\n"
            f"- 领域分类：{category}\n\n"
            "建议替换说法：\n"
            "• 避免绝对化表述（如「总是」「所有」「完全」）\n"
            "• 用「我个人认为」代替直接批判\n"
            "• 补充建设性意见，平衡观点\n"
            "• 可考虑添加免责声明或致歉声明\n"
            "• 删除或模糊化可能引发争议的内容"
        )
        encouragement = "修改后能大幅降低舆情风险，需要我帮你润色文案吗？"

    return {
        "title": title,
        "content": content,
        "encouragement": encouragement
    }


async def analyze_counter_arguments(text: str) -> Dict[str, Any]:
    """
    对抗预演分析：模拟反对者视角分析用户观点。

    返回结构化的对抗预演数据：
    - core_view: 核心观点
    - support_arguments: 支持论据
    - oppose_arguments: 反对论据
    - flaws: 逻辑漏洞分析
    - counter_conclusion: 反对者结论
    """
    def _default_counter() -> Dict[str, Any]:
        return {
            "core_view": "观点分析中...",
            "support_arguments": ["正在生成支持论据"],
            "oppose_arguments": ["正在生成反对论据"],
            "flaws": [{"target": "论据", "flaw": "分析中..."}],
            "counter_conclusion": "反对结论生成中..."
        }

    prompt = f"""你是一位辩论专家，任务是模拟反对者视角，分析以下观点的潜在漏洞。

待分析观点/内容：
{text}

请进行对抗性思考，输出严格JSON格式：
{{
    "core_view": "提炼的核心观点（一句话）",
    "support_arguments": ["支持论据1", "支持论据2", "支持论据3"],
    "oppose_arguments": ["反对论据1", "反对论据2", "反对论据3"],
    "flaws": [
        {{"target": "支持论据1的要点", "flaw": "指出的逻辑漏洞或薄弱环节"}},
        {{"target": "支持论据2的要点", "flaw": "指出的逻辑漏洞或薄弱环节"}},
        {{"target": "支持论据3的要点", "flaw": "指出的逻辑漏洞或薄弱环节"}}
    ],
    "counter_conclusion": "反对者的最终结论（一句话）"
}}

要求：
1. support_arguments 和 oppose_arguments 各生成3条
2. flaws 至少2条，针对支持论据的薄弱环节
3. 输出必须是合法的JSON，不要包含任何其他文本
4. 观点要客观中立，不要有偏见"""

    try:
        response = dashscope.Generation.call(
            model="qwen-max",
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
        )

        if response.status_code != 200:
            logger.error("对抗预演API错误: {}", response)
            return _default_counter()

        content = response.output.choices[0].message.content

        # 提取JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            # 验证必要字段
            result.setdefault("core_view", "无法提炼核心观点")
            result.setdefault("support_arguments", [])
            result.setdefault("oppose_arguments", [])
            result.setdefault("flaws", [])
            result.setdefault("counter_conclusion", "无法生成反对结论")
            logger.info("对抗预演分析完成")
            return result

    except Exception as e:
        logger.exception("对抗预演分析失败: {}", e)

    return _default_counter()
