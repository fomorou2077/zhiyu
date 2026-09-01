from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.notification_service import get_today_hotspots

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationSettings(BaseModel):
    notifications_enabled: bool


@router.get("/today")
async def get_today_notifications(
    current_user: User = Depends(get_current_user),
):
    """获取今日热点推送列表"""
    notifications = await get_today_hotspots()
    return {"notifications": notifications, "shown": True}


@router.get("/settings")
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的通知开关状态"""
    return {"notifications_enabled": current_user.notifications_enabled}


@router.post("/settings")
async def update_notification_settings(
    settings: NotificationSettings,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改用户的通知开关状态"""
    current_user.notifications_enabled = settings.notifications_enabled
    await db.commit()
    return {"success": True, "notifications_enabled": current_user.notifications_enabled}
