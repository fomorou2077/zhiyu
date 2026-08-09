from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models.user import User
from app.models.video_analysis import VideoAnalysis
from app.services.baichuan_service import generate_care_message
from app.utils.logger import logger


# 预设关怀模板（当AI服务不可用时使用）
FALLBACK_CARE_MESSAGES = [
    "🦉 知知注意到你最近的分析频率有所下降，是不是遇到了什么创作瓶颈呢？别担心，知知一直在这里支持你！",
    "🦉 创作路上难免有疲惫的时候。知知建议你可以适当休息一下，调整好状态再继续前行～",
    "🦉 亲爱的创作者，知知发现你的情绪分析中有一些波动的信号。记得照顾好自己，灵感需要好心情来滋养哦！",
    "🦉 每一次创作都是一次成长！知知相信你一定能创作出更多优质内容，加油！",
    "🦉 累了就休息一下，知知会一直守护你的创作之路。有什么问题随时来找我聊聊～",
]


async def check_and_generate_care(user_id: int, db: AsyncSession) -> Optional[dict]:
    """
    检查用户是否需要关怀，如果需要则生成关怀内容。

    触发条件：
    1. 用户超过3天没有收到关怀
    2. 用户最近7天内有分析记录，且风险分数呈上升趋势或焦虑/愤怒情绪较高
    3. 用户超过7天未活跃

    返回：
    - dict: 关怀内容 {message, type, tips}
    - None: 不需要关怀
    """
    try:
        # 1. 获取用户信息
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return None

        # 2. 获取用户近7天的分析记录
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        result = await db.execute(
            select(VideoAnalysis)
            .where(
                VideoAnalysis.user_id == user_id,
                VideoAnalysis.created_at >= seven_days_ago
            )
            .order_by(desc(VideoAnalysis.created_at))
        )
        records = result.scalars().all()

        # 3. 获取上次关怀时间
        last_care = user.last_care_time
        need_care = False
        care_reason = ""

        if not last_care:
            # 首次关怀或从未关怀过
            if len(records) >= 3:
                need_care = True
                care_reason = "welcome"
        elif (datetime.utcnow() - last_care) > timedelta(days=3):
            # 超过3天未关怀
            if len(records) >= 2:
                # 检查风险趋势
                risk_trend = check_risk_trend(records)
                if risk_trend > 0:
                    need_care = True
                    care_reason = "risk_rising"
                elif risk_trend < -10:
                    need_care = True
                    care_reason = "improvement"

            if not need_care and len(records) >= 1:
                avg_risk = sum(r.risk_score for r in records) / len(records)
                if avg_risk > 60:
                    need_care = True
                    care_reason = "high_risk"

        # 4. 检查是否7天未活跃
        if not need_care and last_care and (datetime.utcnow() - last_care) > timedelta(days=7):
            need_care = True
            care_reason = "inactive"

        if not need_care:
            return None

        # 5. 生成关怀内容
        care_type = get_care_type(care_reason, records)
        tips = get_care_tips(care_reason, records)

        try:
            # 尝试调用AI生成关怀语
            care_message = await generate_care_message(
                username=user.username,
                care_type=care_type,
                recent_records=[{"risk_score": r.risk_score, "emotions": r.emotions} for r in records[:5]]
            )
        except Exception as e:
            logger.warning("AI关怀生成失败，使用预设模板: {}", e)
            import random
            care_message = random.choice(FALLBACK_CARE_MESSAGES)

        # 6. 更新关怀时间
        user.last_care_time = datetime.utcnow()
        await db.commit()

        return {
            "message": care_message,
            "type": care_type,
            "tips": tips,
            "reason": care_reason,
            "has_records": len(records) > 0
        }

    except Exception as e:
        logger.exception("检查关怀时出错: {}", e)
        return None


def check_risk_trend(records: list) -> float:
    """检查风险分数趋势，返回变化量"""
    if len(records) < 2:
        return 0

    recent = records[0].risk_score
    older = records[-1].risk_score
    return recent - older


def get_care_type(reason: str, records: list) -> str:
    """根据原因获取关怀类型"""
    type_mapping = {
        "welcome": "encouragement",
        "risk_rising": "warning",
        "improvement": "celebration",
        "high_risk": "support",
        "inactive": "reminder"
    }
    return type_mapping.get(reason, "general")


def get_care_tips(reason: str, records: list) -> list:
    """根据原因获取关怀建议"""
    tips_map = {
        "welcome": ["坚持每周分析2-3个视频", "保持创作节奏", "有问题随时找知知"],
        "risk_rising": ["注意内容风险点", "适当调整表达方式", "知知随时为你分析"],
        "improvement": ["继续保持这个状态", "分析技巧越来越好了", "知知为你骄傲"],
        "high_risk": ["建议降低视频发布频率", "仔细检查内容合规性", "知知可以帮你再次分析"],
        "inactive": ["知知很想你呀～", "今天来创作一个视频吧", "有任何问题知知都在"]
    }
    return tips_map.get(reason, ["照顾好自己", "知知一直在你身边", "加油创作者"])
