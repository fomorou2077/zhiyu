from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.utils.logger import logger
from app.utils.security import decode_access_token as decode_token

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    privacy_mode_default: bool = False
    notifications_enabled: bool = True


class SettingsResponse(BaseModel):
    privacy_mode_default: bool
    notifications_enabled: bool


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


@router.get("", response_model=SettingsResponse)
async def get_settings(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户的设置。
    """
    try:
        user_id = get_user_id_from_token(authorization)
    except HTTPException:
        raise HTTPException(status_code=401, detail="请先登录")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return SettingsResponse(
        privacy_mode_default=user.privacy_mode_default,
        notifications_enabled=user.notifications_enabled
    )


@router.post("")
async def update_settings(
    settings: SettingsUpdate,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    修改用户的设置。
    """
    try:
        user_id = get_user_id_from_token(authorization)
    except HTTPException:
        raise HTTPException(status_code=401, detail="请先登录")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.privacy_mode_default = settings.privacy_mode_default
    user.notifications_enabled = settings.notifications_enabled
    await db.commit()

    return {
        "success": True,
        "privacy_mode_default": user.privacy_mode_default,
        "notifications_enabled": user.notifications_enabled
    }
