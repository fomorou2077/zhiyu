from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, MotivationResponse
from app.services.baichuan_service import chat_with_ai
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    _ = db
    messages = [
        {
            "role": "system",
            "content": (
                "你是知舆系统的AI助手“知知”，一只智慧的猫头鹰。"
                "你帮助自媒体作者分析视频舆论风险，提供情绪支持。"
                "回答要温暖、专业、有同理心。"
            ),
        }
    ]
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": request.message})
    reply = await chat_with_ai(messages)
    return ChatResponse(reply=reply)


@router.get("/motivation", response_model=MotivationResponse)
async def get_motivation(user_id: int = 1, db: AsyncSession = Depends(get_db)):
    """
    获取针对用户的个性化鼓励语
    """
    from app.models.video_analysis import VideoAnalysis
    from app.models.monitor import MonitorRecord

    # 总分析次数
    total_row = await db.execute(
        select(func.count(VideoAnalysis.id)).where(VideoAnalysis.user_id == user_id)
    )
    total = total_row.scalar() or 0

    # 近一周上传数
    week_ago = datetime.now() - timedelta(days=7)
    recent_row = await db.execute(
        select(func.count(VideoAnalysis.id)).where(
            VideoAnalysis.user_id == user_id,
            VideoAnalysis.created_at >= week_ago,
        )
    )
    recent = recent_row.scalar() or 0

    # 平均风险分数（最近3次）
    risks_row = await db.execute(
        select(VideoAnalysis.risk_score)
        .where(VideoAnalysis.user_id == user_id, VideoAnalysis.risk_score.isnot(None))
        .order_by(VideoAnalysis.created_at.desc())
        .limit(3)
    )
    risks = [r[0] for r in risks_row.fetchall() if r[0] is not None]
    avg_risk = sum(risks) / len(risks) if risks else None

    # 监测记录数
    monitored_row = await db.execute(
        select(func.count(MonitorRecord.id)).where(MonitorRecord.user_id == user_id)
    )
    monitored = monitored_row.scalar() or 0

    # 生成鼓励语
    templates = []

    if total == 0:
        templates.append(
            "🌟 欢迎来到知舆！上传第一个视频，开启你的舆情守护之旅。"
        )
    else:
        templates.append(
            f"📊 你已经分析了 {total} 个视频，持续进步中！"
        )

    if recent > 0:
        templates.append(
            f"🔥 最近一周上传了 {recent} 个视频，创作热情高涨！"
        )

    if avg_risk is not None:
        if avg_risk < 30:
            templates.append(
                "✨ 你的视频风险控制得非常好，继续保持！"
            )
        elif avg_risk > 70:
            templates.append(
                "🌱 近期视频风险略高，发布前建议用多模态分析，我会陪你一起调整内容。"
            )

    if monitored > 0:
        templates.append(
            f"📢 你已监测 {monitored} 个已发布视频，及时了解观众反馈，超棒！"
        )

    if not templates:
        templates.append(
            "🦉 知知一直在关注你的创作，有任何问题随时找我聊天~"
        )

    return MotivationResponse(motivation=random.choice(templates))
