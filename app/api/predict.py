"""
热度预测 API 路由
基于阿里云百炼大模型实现
"""

from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter
from app.services.baichuan_service import chat_with_ai
from app.utils.logger import logger

router = APIRouter(prefix="/predict", tags=["热度预测"])


class PredictRequest(BaseModel):
    """热度预测请求模型"""
    title: str
    tags: List[str] = []
    category: str = "general"
    description: str = ""
    duration: int = 300
    author_avg_heat: int = 100


class PredictResponse(BaseModel):
    """热度预测响应模型"""
    success: bool
    hours: List[str]
    predicted_heat: List[int]
    risk: str
    risk_level: str
    similar_videos: List[str]
    summary: str
    keywords: List[str]


# 模拟历史视频库（与 predict_app.py 一致）
HISTORY_VIDEOS = [
    {
        "id": 1,
        "summary": "这是一部关于Python编程入门的教学视频",
        "heat_curve": [45, 30, 25, 20, 18, 35, 80, 150, 200, 180, 160, 140, 120, 110, 100, 95, 85, 70, 55, 40, 35, 30, 28, 25],
        "risk_level": "低",
        "tags": ["编程", "Python", "教程", "入门"]
    },
    {
        "id": 2,
        "summary": "这是一部关于游戏直播的娱乐搞笑视频",
        "heat_curve": [120, 100, 90, 85, 80, 95, 140, 220, 280, 260, 240, 210, 180, 160, 145, 130, 120, 110, 95, 80, 70, 65, 60, 55],
        "risk_level": "中",
        "tags": ["游戏", "直播", "搞笑", "娱乐"]
    },
    {
        "id": 3,
        "summary": "这是一部探讨社会热点话题的评论视频",
        "heat_curve": [200, 180, 160, 150, 145, 200, 350, 500, 600, 550, 480, 420, 380, 350, 320, 290, 260, 230, 200, 180, 160, 150, 140, 130],
        "risk_level": "高",
        "tags": ["社会", "热点", "评论", "争议"]
    },
    {
        "id": 4,
        "summary": "这是一部美食制作教程视频",
        "heat_curve": [35, 25, 20, 18, 15, 22, 45, 90, 140, 160, 150, 135, 120, 105, 95, 85, 75, 65, 55, 48, 42, 38, 35, 32],
        "risk_level": "低",
        "tags": ["美食", "烹饪", "教程", "家常菜"]
    },
    {
        "id": 5,
        "summary": "这是一部科技产品测评视频",
        "heat_curve": [60, 45, 38, 32, 28, 35, 70, 120, 180, 200, 185, 165, 145, 130, 115, 100, 90, 80, 70, 62, 55, 50, 48, 45],
        "risk_level": "低",
        "tags": ["科技", "测评", "数码", "产品"]
    },
    {
        "id": 6,
        "summary": "这是一部健身减脂教程视频",
        "heat_curve": [50, 40, 35, 30, 28, 32, 55, 100, 150, 170, 155, 140, 125, 110, 100, 90, 80, 70, 62, 55, 50, 45, 42, 40],
        "risk_level": "低",
        "tags": ["健身", "减肥", "健康", "运动"]
    },
    {
        "id": 7,
        "summary": "这是一部探讨明星绯闻的娱乐八卦视频",
        "heat_curve": [300, 280, 260, 250, 240, 300, 450, 600, 700, 680, 620, 560, 500, 450, 400, 360, 320, 290, 260, 240, 220, 210, 200, 190],
        "risk_level": "高",
        "tags": ["娱乐", "明星", "八卦", "绯闻"]
    },
    {
        "id": 8,
        "summary": "这是一部儿童动画教育视频",
        "heat_curve": [80, 120, 150, 140, 130, 125, 120, 115, 110, 105, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 48, 45, 42],
        "risk_level": "低",
        "tags": ["儿童", "动画", "教育", "早教"]
    },
    {
        "id": 9,
        "summary": "这是一部美妆教程视频",
        "heat_curve": [55, 48, 42, 38, 35, 40, 65, 110, 160, 180, 165, 150, 135, 120, 108, 95, 85, 75, 68, 60, 55, 50, 48, 45],
        "risk_level": "低",
        "tags": ["美妆", "化妆", "教程", "女性"]
    },
    {
        "id": 10,
        "summary": "这是一部探讨政治话题的严肃评论视频",
        "heat_curve": [180, 160, 145, 135, 130, 180, 320, 480, 580, 540, 490, 440, 400, 360, 330, 300, 270, 245, 220, 200, 185, 175, 165, 155],
        "risk_level": "高",
        "tags": ["政治", "评论", "严肃", "分析"]
    },
    {
        "id": 11,
        "summary": "这是一部旅游 vlog 视频",
        "heat_curve": [40, 32, 28, 25, 22, 28, 50, 95, 145, 165, 150, 135, 120, 108, 98, 88, 78, 68, 60, 52, 46, 42, 40, 38],
        "risk_level": "低",
        "tags": ["旅游", "vlog", "风景", "旅行"]
    },
    {
        "id": 12,
        "summary": "这是一部汽车测评视频",
        "heat_curve": [65, 52, 45, 40, 35, 42, 75, 130, 190, 210, 195, 175, 155, 140, 125, 112, 100, 90, 80, 70, 62, 58, 55, 52],
        "risk_level": "低",
        "tags": ["汽车", "测评", "试驾", "新车"]
    },
    {
        "id": 13,
        "summary": "这是一部探讨情感话题的脱口秀视频",
        "heat_curve": [95, 85, 78, 72, 68, 75, 110, 170, 230, 250, 235, 210, 190, 170, 155, 140, 128, 115, 105, 95, 88, 82, 78, 75],
        "risk_level": "中",
        "tags": ["情感", "脱口秀", "话题", "生活"]
    },
    {
        "id": 14,
        "summary": "这是一部音乐翻唱视频",
        "heat_curve": [70, 60, 55, 50, 48, 55, 90, 150, 210, 235, 220, 200, 180, 162, 145, 130, 118, 105, 95, 85, 78, 72, 68, 65],
        "risk_level": "低",
        "tags": ["音乐", "翻唱", "歌曲", "演唱"]
    },
    {
        "id": 15,
        "summary": "这是一部揭秘网红造假事件的视频",
        "heat_curve": [250, 230, 210, 200, 195, 260, 420, 580, 650, 620, 570, 520, 470, 425, 385, 350, 315, 285, 255, 235, 215, 200, 190, 180],
        "risk_level": "高",
        "tags": ["网红", "揭秘", "造假", "事件"]
    },
    {
        "id": 16,
        "summary": "这是一部手工DIY制作教程视频",
        "heat_curve": [38, 30, 25, 22, 20, 25, 48, 88, 135, 155, 142, 128, 115, 102, 92, 82, 73, 64, 56, 50, 45, 42, 40, 38],
        "risk_level": "低",
        "tags": ["手工", "DIY", "制作", "教程"]
    },
    {
        "id": 17,
        "summary": "这是一部职场技能提升教程视频",
        "heat_curve": [42, 35, 30, 28, 25, 30, 55, 100, 155, 175, 162, 148, 132, 118, 105, 95, 85, 75, 66, 58, 52, 48, 45, 42],
        "risk_level": "低",
        "tags": ["职场", "技能", "提升", "工作"]
    },
    {
        "id": 18,
        "summary": "这是一部测评争议商品的视频",
        "heat_curve": [150, 135, 125, 118, 115, 165, 280, 420, 520, 490, 450, 405, 365, 330, 300, 272, 245, 220, 198, 180, 165, 155, 148, 140],
        "risk_level": "中",
        "tags": ["测评", "争议", "商品", "对比"]
    },
    {
        "id": 19,
        "summary": "这是一部萌宠日常记录视频",
        "heat_curve": [55, 48, 42, 38, 35, 40, 65, 115, 170, 195, 180, 162, 145, 130, 118, 105, 95, 85, 75, 66, 60, 55, 52, 50],
        "risk_level": "低",
        "tags": ["宠物", "萌宠", "猫狗", "可爱"]
    },
    {
        "id": 20,
        "summary": "这是一部探讨地域歧视话题的视频",
        "heat_curve": [220, 200, 185, 175, 170, 230, 380, 550, 640, 610, 560, 510, 460, 415, 375, 340, 305, 275, 248, 225, 208, 195, 185, 175],
        "risk_level": "高",
        "tags": ["地域", "歧视", "争议", "话题"]
    },
]


def find_similar_videos(keywords: List[str], limit: int = 3) -> list:
    """根据关键词检索相似视频"""
    scored_videos = []

    for video in HISTORY_VIDEOS:
        score = 0
        for kw in keywords:
            if kw in video['summary'] or kw in video['tags']:
                score += 10

        if score > 0:
            scored_videos.append((video, score))

    scored_videos.sort(key=lambda x: x[1], reverse=True)
    return [v[0] for v in scored_videos[:limit]]


def predict_heat_curve(similar_videos: list, author_avg_heat: int) -> List[int]:
    """基于相似视频预测热度曲线"""
    if not similar_videos:
        base_curve = [30, 25, 22, 20, 18, 25, 50, 100, 150, 170, 155, 140,
                      125, 110, 100, 90, 80, 70, 60, 52, 45, 40, 35, 32]
    else:
        avg_curve = []
        for i in range(24):
            avg_val = sum(v['heat_curve'][i] for v in similar_videos) / len(similar_videos)
            avg_curve.append(avg_val)
        base_curve = avg_curve

    if author_avg_heat > 0:
        scale_factor = author_avg_heat / 100
        adjusted_curve = [int(h * scale_factor) for h in base_curve]
    else:
        adjusted_curve = [int(h) for h in base_curve]

    return adjusted_curve


def generate_risk_advice(keywords: List[str]) -> tuple:
    """生成风险建议"""
    high_risk_keywords = ['争议', '敏感', '政治', '歧视', '绯闻', '造假', '地域', '社会']
    medium_risk_keywords = ['明星', '八卦', '对比', '测评', '评论', '话题']

    detected_risks = []
    for kw in keywords:
        if kw in high_risk_keywords:
            detected_risks.append(('高', kw))
        elif kw in medium_risk_keywords:
            detected_risks.append(('中', kw))

    if any(r[0] == '高' for r in detected_risks):
        risk_level = '高风险'
        advice = '内容涉及敏感话题，建议谨慎发布。可能引发争议，请确保内容合规。'
    elif any(r[0] == '中' for r in detected_risks):
        risk_level = '中风险'
        advice = '内容有一定话题性，建议适度把握尺度。注意避免涉及版权或隐私问题。'
    else:
        risk_level = '低风险'
        advice = '内容健康正面，发布风险较低。建议保持稳定的更新频率。'

    return f"{risk_level}：{advice}", risk_level


async def analyze_with_llm(title: str, tags: List[str], description: str) -> tuple:
    """使用百炼大模型分析视频内容"""
    prompt = f"""你是一位专业的自媒体内容分析师。请分析以下视频内容并给出：
1. 内容概括（一句话）
2. 关键词（5个以内）

视频信息：
标题：{title}
标签：{', '.join(tags) if tags else '无'}
描述：{description}

请严格以JSON格式输出：
{{"summary": "概括内容", "keywords": ["关键词1", "关键词2", "关键词3"]}}

只输出JSON，不要其他内容。"""

    try:
        result = await chat_with_ai(
            messages=[{"role": "user", "content": prompt}],
            enable_search=False,
            model="qwen-turbo"
        )

        import json
        import re
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return data.get("summary", ""), data.get("keywords", [])
    except Exception as e:
        logger.warning("LLM分析失败: {}", e)

    # 降级处理
    all_keywords = list(set(tags))[:5] if tags else ["视频"]
    return f"关于{title}的视频内容", all_keywords


@router.post("/ai-predict", response_model=PredictResponse)
async def ai_predict(request: PredictRequest):
    """
    AI 辅助视频热度预测接口

    - 分析视频内容
    - 查找相似历史视频
    - 预测24小时热度曲线
    - 生成风险评估
    """
    try:
        logger.info("热度预测请求: title={}", request.title)

        # 1. 使用 LLM 分析内容（如果提供了足够的描述）
        if request.description or len(request.tags) >= 2:
            summary, keywords = await analyze_with_llm(
                request.title,
                request.tags,
                request.description
            )
        else:
            # 降级：使用规则分析
            keywords = list(set(request.tags))[:5] if request.tags else ["视频"]
            summary = f"关于{request.title}的视频内容"

        logger.info("内容分析完成: summary={}, keywords={}", summary, keywords)

        # 2. 查找相似视频
        similar_videos = find_similar_videos(keywords)
        logger.info("找到 {} 个相似视频", len(similar_videos))

        # 3. 预测热度曲线
        predicted_heat = predict_heat_curve(similar_videos, request.author_avg_heat)
        logger.info("热度预测完成: 峰值={}", max(predicted_heat) if predicted_heat else 0)

        # 4. 生成风险建议
        risk_advice, risk_level = generate_risk_advice(keywords)
        logger.info("风险评估: level={}", risk_level)

        # 5. 构建响应
        hours = [f"{h:02d}:00" for h in range(24)]
        similar_names = [
            v['summary'].replace('这是一部关于', '').replace('的视频', '')
            for v in similar_videos[:3]
        ]

        return PredictResponse(
            success=True,
            hours=hours,
            predicted_heat=predicted_heat,
            risk=risk_advice,
            risk_level=risk_level,
            similar_videos=similar_names,
            summary=summary,
            keywords=keywords
        )

    except Exception as e:
        logger.exception("热度预测失败: {}", e)
        return PredictResponse(
            success=False,
            hours=[],
            predicted_heat=[],
            risk="预测失败，请稍后重试",
            risk_level="未知",
            similar_videos=[],
            summary="",
            keywords=[]
        )
