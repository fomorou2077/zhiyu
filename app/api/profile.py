from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.video_analysis import VideoAnalysis
from app.models.monitor import MonitorRecord
from app.schemas.profile import (
    TrendPoint,
    CreatorStatsResponse,
    VideoHeat,
    MonthlyHeatPoint,
)
from app.utils.logger import logger

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/trends", response_model=List[TrendPoint])
async def get_emotion_trends(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    _ = db
    points = []
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        points.append(
            TrendPoint(
                date=date,
                emotions={"joy": 5 + i % 3, "anxiety": 3 + i % 2},
            )
        )
    return points


@router.get("/creator-stats", response_model=CreatorStatsResponse)
async def get_creator_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取创作者数据分析"""
    user_id = current_user.id
    logger.info("获取创作者统计数据: user_id={}", user_id)

    result = await db.execute(
        select(VideoAnalysis).where(VideoAnalysis.user_id == user_id)
    )
    user_analyses = result.scalars().all()

    result = await db.execute(
        select(MonitorRecord).where(MonitorRecord.user_id == user_id)
    )
    monitor_records = result.scalars().all()

    if not user_analyses and not monitor_records:
        return CreatorStatsResponse(
            domain="未确定",
            ranking=0,
            total_creators=0,
            monthly_heat_trend=[],
            best_video=None,
            worst_video=None,
            suggestions="上传一些视频或监测已发布视频，我们会为你生成分析。",
            total_videos=0,
            total_likes=0,
            total_comments=0,
            avg_risk_score=0.0,
        )

    categories = [a.category for a in user_analyses if a.category]
    if categories:
        domain = Counter(categories).most_common(1)[0][0]
    else:
        domain = "其他"

    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_monitors = [r for r in monitor_records if r.created_at and r.created_at >= thirty_days_ago]

    trend_by_date = defaultdict(lambda: {"likes": 0, "comments": 0, "risk": 0, "count": 0})
    for rec in recent_monitors:
        if rec.created_at:
            date_key = rec.created_at.date()
            trend_by_date[date_key]["likes"] += rec.like_count or 0
            trend_by_date[date_key]["comments"] += rec.comment_count or 0
            trend_by_date[date_key]["risk"] += rec.risk_score or 0
            trend_by_date[date_key]["count"] += 1

    monthly_heat_trend = []
    for date_key in sorted(trend_by_date.keys()):
        data = trend_by_date[date_key]
        monthly_heat_trend.append(
            MonthlyHeatPoint(
                date=date_key.isoformat(),
                avg_likes=round(data["likes"] / data["count"], 1),
                avg_comments=round(data["comments"] / data["count"], 1),
                avg_risk=round(data["risk"] / data["count"], 1),
            )
        )

    videos = []
    for a in user_analyses:
        created_date = a.created_at.date() if a.created_at else datetime.now().date()
        score = max(0, 100 - (a.risk_score or 50))
        videos.append({
            "id": a.id,
            "title": a.file_name or "未命名视频",
            "like_count": 0,
            "comment_count": 0,
            "risk_score": a.risk_score or 0,
            "created_at": created_date,
            "score": score,
            "source": "analysis",
        })

    for r in monitor_records:
        created_date = r.created_at.date() if r.created_at else datetime.now().date()
        score = (r.like_count or 0) * 0.5 + (r.comment_count or 0) * 0.3 - (r.risk_score or 0) * 0.2
        videos.append({
            "id": r.id,
            "title": r.title or "未命名视频",
            "like_count": r.like_count or 0,
            "comment_count": r.comment_count or 0,
            "risk_score": r.risk_score or 0,
            "created_at": created_date,
            "score": score,
            "source": "monitor",
        })

    best_video: Optional[VideoHeat] = None
    worst_video: Optional[VideoHeat] = None

    if videos:
        best = max(videos, key=lambda x: x["score"])
        worst = min(videos, key=lambda x: x["score"])

        best_video = VideoHeat(
            video_id=best["id"],
            title=best["title"],
            like_count=best["like_count"],
            comment_count=best["comment_count"],
            risk_score=best["risk_score"],
            created_at=best["created_at"],
            score=round(best["score"], 1),
        )

        worst_video = VideoHeat(
            video_id=worst["id"],
            title=worst["title"],
            like_count=worst["like_count"],
            comment_count=worst["comment_count"],
            risk_score=worst["risk_score"],
            created_at=worst["created_at"],
            score=round(worst["score"], 1),
        )

    total_videos = len(videos)
    total_likes = sum(v.get("like_count", 0) for v in videos)
    total_comments = sum(v.get("comment_count", 0) for v in videos)
    avg_risk = sum(v.get("risk_score", 0) for v in videos) / total_videos if total_videos > 0 else 0.0

    ranking = 1
    total_creators = 1
    result2 = await db.execute(
        select(func.count(func.distinct(VideoAnalysis.user_id)))
    )
    user_count = result2.scalar() or 1
    total_creators = max(1, user_count)

    suggestions = _generate_suggestions(domain, best_video, worst_video, avg_risk, total_videos)

    return CreatorStatsResponse(
        domain=domain,
        ranking=ranking,
        total_creators=total_creators,
        monthly_heat_trend=monthly_heat_trend,
        best_video=best_video,
        worst_video=worst_video,
        suggestions=suggestions,
        total_videos=total_videos,
        total_likes=total_likes,
        total_comments=total_comments,
        avg_risk_score=round(avg_risk, 1),
    )


def _generate_suggestions(
    domain: str,
    best_video: Optional[VideoHeat],
    worst_video: Optional[VideoHeat],
    avg_risk: float,
    total_videos: int,
) -> str:
    """根据数据生成个性化建议"""
    suggestions = []

    domain_advice = {
        "政治": "政治类内容需格外注意言论合规性，建议多参考官方媒体表述。",
        "社会": "社会热点话题关注度高，建议保持客观理性，避免过度情绪化。",
        "娱乐": "娱乐内容竞争激烈，建议突出个人特色，保持更新频率。",
        "科技": "科技内容需要准确性，建议引用权威来源，避免传播未经证实的信息。",
        "游戏": "游戏内容受众活跃，建议多与观众互动，关注游戏圈热点。",
        "生活": "生活类内容覆盖面广，建议找准细分领域，建立差异化优势。",
        "教育": "教育内容需确保知识准确性，建议增加实用性，避免误导。",
        "其他": "建议持续产出优质内容，逐步建立自己的创作风格。",
    }

    suggestions.append(domain_advice.get(domain, domain_advice["其他"]))

    if best_video:
        suggestions.append(f"您的视频「{best_video.title}」表现优异，可以分析其成功因素并复制。")

    if worst_video:
        if worst_video.risk_score > 60:
            suggestions.append(f"「{worst_video.title}」风险评分较高，建议检查内容是否符合平台规范。")
        elif worst_video.like_count < 100:
            suggestions.append(f"「{worst_video.title}」互动较低，可以尝试优化标题和封面。")

    if avg_risk > 70:
        suggestions.append("您的整体风险评分偏高，建议在发布前更加谨慎审核内容。")
    elif avg_risk < 30:
        suggestions.append("您的风险控制做得很好，继续保持！")

    if total_videos < 3:
        suggestions.append("数据积累还不够，建议多上传/监测几个视频以获得更精准的分析。")

    return " ".join(suggestions)


@router.get("/summary")
async def get_profile_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取档案摘要"""
    user_id = current_user.id

    result = await db.execute(
        select(VideoAnalysis).where(VideoAnalysis.user_id == user_id)
    )
    analyses = result.scalars().all()

    result = await db.execute(
        select(MonitorRecord).where(MonitorRecord.user_id == user_id)
    )
    monitors = result.scalars().all()

    categories = [a.category for a in analyses if a.category]
    domain = Counter(categories).most_common(1)[0][0] if categories else "其他"

    return {
        "total_analyses": len(analyses),
        "total_monitors": len(monitors),
        "domain": domain,
        "avg_risk": round(sum(a.risk_score or 0 for a in analyses) / len(analyses), 1) if analyses else 0,
    }
