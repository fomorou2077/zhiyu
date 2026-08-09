from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.services.notification_service import get_today_hotspots, should_show_notification
from app.utils.logger import logger
from app.utils.security import decode_access_token as decode_token

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationSettings(BaseModel):
    notifications_enabled: bool


class SettingsUpdate(BaseModel):
    privacy_mode_default: bool = False
    notifications_enabled: bool = True


def get_user_id_from_token(authorization: str) -> int:
    """从 Authorization header 中提取 user_id"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="无效的token")

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效的用户")

        return int(user_id)

    except Exception:
        raise HTTPException(status_code=401, detail="认证失败")


@router.get("/today")
async def get_today_notifications(authorization: str = Header(...)):
    """
    获取今日热点推送列表。
    """
    try:
        user_id = get_user_id_from_token(authorization)
    except HTTPException:
        return {"notifications": [], "shown": False}

    notifications = await get_today_hotspots()

    return {
        "notifications": notifications,
        "shown": True
    }


@router.get("/settings")
async def get_notification_settings(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户的通知开关状态。
    """
    try:
        user_id = get_user_id_from_token(authorization)
    except HTTPException:
        raise HTTPException(status_code=401, detail="请先登录")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "notifications_enabled": user.notifications_enabled
    }


@router.post("/settings")
async def update_notification_settings(
    settings: NotificationSettings,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    修改用户的通知开关状态。
    """
    try:
        user_id = get_user_id_from_token(authorization)
    except HTTPException:
        raise HTTPException(status_code=401, detail="请先登录")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.notifications_enabled = settings.notifications_enabled
    await db.commit()

    return {"success": True, "notifications_enabled": user.notifications_enabled}