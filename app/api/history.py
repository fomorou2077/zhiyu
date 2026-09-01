from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.video_analysis import VideoAnalysis
from app.schemas.video import VideoAnalysisResponse

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/", response_model=List[VideoAnalysisResponse])
async def list_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(VideoAnalysis)
        .where(VideoAnalysis.user_id == current_user.id)
        .order_by(VideoAnalysis.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    records = result.scalars().all()
    return [VideoAnalysisResponse.model_validate(r) for r in records]


@router.get("/{record_id}", response_model=VideoAnalysisResponse)
async def get_history_detail(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await db.get(VideoAnalysis, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此记录")
    return VideoAnalysisResponse.model_validate(record)
