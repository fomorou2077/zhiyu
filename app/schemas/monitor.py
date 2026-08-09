from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class MonitorRequest(BaseModel):
    """监测请求参数"""
    url: str = Field(..., description="视频链接，支持小红书、抖音、B站等")


class MonitorResponse(BaseModel):
    """监测响应数据"""
    id: int
    platform: str
    video_id: str
    title: str
    cover_url: Optional[str] = None
    like_count: int
    comment_count: int
    analysis: Dict[str, Any]
    created_at: str


class VideoInfo(BaseModel):
    """视频信息模型"""
    platform: str
    video_id: str
    title: str
    cover_url: Optional[str] = None
    like_count: int
    comment_count: int
    comments: List[str] = []


class MonitorRecordResponse(BaseModel):
    """监测记录列表项"""
    id: int
    platform: str
    title: str
    like_count: int
    comment_count: int
    risk_score: int
    created_at: str
