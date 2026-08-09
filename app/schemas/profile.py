from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


class TrendPoint(BaseModel):
    date: str
    emotions: Dict[str, float]


# ============================================
# 创作者数据分析相关 Schema
# ============================================

class VideoHeat(BaseModel):
    """视频热度数据"""
    video_id: int
    title: str
    like_count: int
    comment_count: int
    risk_score: int
    created_at: date
    score: float  # 综合热度得分


class MonthlyHeatPoint(BaseModel):
    """月度热度趋势数据点"""
    date: str
    avg_likes: float
    avg_comments: float
    avg_risk: float


class CreatorStatsResponse(BaseModel):
    """创作者统计数据响应"""
    domain: str  # 创作领域
    ranking: int  # 在同类中的排名（1为最高）
    total_creators: int  # 同类创作者总数
    monthly_heat_trend: List[MonthlyHeatPoint]  # 近30天热度趋势
    best_video: Optional[VideoHeat]
    worst_video: Optional[VideoHeat]
    suggestions: str  # 改进建议
    total_videos: int  # 视频总数
    total_likes: int  # 总点赞数
    total_comments: int  # 总评论数
    avg_risk_score: float  # 平均风险分数
