from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    privacy_mode_default: bool = False
    notifications_enabled: bool = True


class SettingsResponse(BaseModel):
    privacy_mode_default: bool
    notifications_enabled: bool


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的设置"""
    return SettingsResponse(
        privacy_mode_default=current_user.privacy_mode_default,
        notifications_enabled=current_user.notifications_enabled
    )


@router.post("")
async def update_settings(
    settings: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改用户的设置"""
    current_user.privacy_mode_default = settings.privacy_mode_default
    current_user.notifications_enabled = settings.notifications_enabled
    await db.commit()

    return {
        "success": True,
        "privacy_mode_default": current_user.privacy_mode_default,
        "notifications_enabled": current_user.notifications_enabled
    }
