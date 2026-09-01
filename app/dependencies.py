"""
统一认证依赖注入模块
所有需要认证的端点统一使用这里的 Depends(get_current_user)
"""
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.utils.security import decode_access_token, get_password_hash

security = HTTPBearer(auto_error=False)

# 缓存Demo用户ID，避免每次请求都查库
_demo_user_id = None


async def _get_or_create_demo_user(db: AsyncSession) -> User:
    """获取或创建Demo企业版用户"""
    global _demo_user_id
    if _demo_user_id:
        result = await db.execute(select(User).where(User.id == _demo_user_id))
        user = result.scalar_one_or_none()
        if user:
            return user

    # 查找或创建demo用户
    result = await db.execute(select(User).where(User.email == "demo@enterprise.local"))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email="demo@enterprise.local",
            phone="13800000000",
            username="Demo企业",
            hashed_password=get_password_hash("demo123456"),
            user_type="enterprise",
            subscription_tier="enterprise",
            trial_started_at=datetime.utcnow(),
            subscription_expiry=datetime.utcnow() + timedelta(days=30),
            enterprise_brand="知舆科技",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    _demo_user_id = user.id
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Bearer token 解析当前用户；Demo模式下无token时自动使用Demo企业用户"""
    # 正常JWT认证流程
    if credentials:
        payload = decode_access_token(credentials.credentials)
        if payload:
            user_id = payload.get("user_id")
            if user_id:
                result = await db.execute(select(User).where(User.id == int(user_id)))
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user

    # Demo模式：无token或token无效时，返回Demo企业用户
    if settings.demo_mode:
        return await _get_or_create_demo_user(db)

    raise HTTPException(status_code=401, detail="未提供认证凭据")


async def get_current_enterprise_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求企业版用户身份"""
    if current_user.user_type != "enterprise":
        raise HTTPException(status_code=403, detail="此功能仅限企业版用户使用")
    return current_user


async def get_current_personal_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求个人版用户身份（企业版用户也可访问个人版功能）"""
    return current_user
