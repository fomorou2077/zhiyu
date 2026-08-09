"""
监测 API - 用于监测已发布视频的评论和舆情
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.monitor import MonitorRecord
from app.models.user import User
from app.schemas.monitor import (
    MonitorRequest,
    MonitorResponse,
    MonitorRecordResponse
)
from app.services.crawler import fetch_video_info
from app.services.emotion_analyzer import analyze_comments
from app.utils.logger import logger

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.post("/fetch", response_model=MonitorResponse)
async def fetch_and_analyze(request: MonitorRequest, db: AsyncSession = Depends(get_db)):
    """
    监测视频接口
    
    1. 抓取视频信息和评论
    2. 分析评论情绪
    3. 保存监测记录
    4. 返回分析结果
    """
    try:
        # 1. 抓取视频信息（包括评论）
        logger.info("开始抓取视频信息: {}", request.url)
        video_info = await fetch_video_info(request.url)
        
        # 2. 分析评论情绪
        logger.info("开始分析评论情绪，共 {} 条评论", len(video_info.comments))
        analysis = await analyze_comments(video_info.comments)
        
        # 3. 获取用户ID（临时使用用户ID=1）
        user_id = 1
        
        # 4. 保存监测记录
        record = MonitorRecord(
            user_id=user_id,
            platform=video_info.platform,
            video_url=request.url,
            video_id=video_info.video_id,
            title=video_info.title,
            cover_url=video_info.cover_url,
            like_count=video_info.like_count,
            comment_count=video_info.comment_count,
            comment_analysis=analysis,
            risk_score=analysis.get("risk_score", 0)
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        
        logger.info("监测记录保存成功: id={}, title={}", record.id, record.title)
        
        # 5. 返回结果
        return MonitorResponse(
            id=record.id,
            platform=record.platform,
            video_id=record.video_id,
            title=record.title,
            cover_url=record.cover_url,
            like_count=record.like_count,
            comment_count=record.comment_count,
            analysis=analysis,
            created_at=record.created_at.isoformat() if record.created_at else datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.exception("监测失败: {}", e)
        raise HTTPException(status_code=500, detail=f"监测失败: {str(e)}")


@router.get("/records", response_model=List[MonitorRecordResponse])
async def get_monitor_records(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    获取监测记录列表
    
    Args:
        limit: 返回记录数量限制，默认20条
    """
    try:
        # 临时使用用户ID=1
        user_id = 1
        
        result = await db.execute(
            select(MonitorRecord)
            .where(MonitorRecord.user_id == user_id)
            .order_by(desc(MonitorRecord.created_at))
            .limit(limit)
        )
        records = result.scalars().all()
        
        return [
            MonitorRecordResponse(
                id=record.id,
                platform=record.platform,
                title=record.title,
                like_count=record.like_count,
                comment_count=record.comment_count,
                risk_score=record.risk_score or 0,
                created_at=record.created_at.isoformat() if record.created_at else ""
            )
            for record in records
        ]
    except Exception as e:
        logger.exception("获取监测记录失败: {}", e)
        raise HTTPException(status_code=500, detail=f"获取监测记录失败: {str(e)}")


@router.get("/records/{record_id}")
async def get_monitor_record_detail(record_id: int, db: AsyncSession = Depends(get_db)):
    """
    获取单条监测记录的详细信息
    """
    try:
        result = await db.execute(
            select(MonitorRecord).where(MonitorRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        
        return {
            "id": record.id,
            "platform": record.platform,
            "video_id": record.video_id,
            "title": record.title,
            "cover_url": record.cover_url,
            "like_count": record.like_count,
            "comment_count": record.comment_count,
            "comment_analysis": record.comment_analysis,
            "risk_score": record.risk_score or 0,
            "created_at": record.created_at.isoformat() if record.created_at else ""
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取监测记录详情失败: {}", e)
        raise HTTPException(status_code=500, detail=f"获取监测记录详情失败: {str(e)}")
