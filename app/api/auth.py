from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import (
    SwitchVersionRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.utils.logger import logger
from app.utils.security import create_access_token, get_password_hash, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """用户注册，默认创建个人版账号"""
    # 检查邮箱是否已注册
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="邮箱已注册")

    # 检查手机号是否已注册
    if user_data.phone:
        result = await db.execute(select(User).where(User.phone == user_data.phone))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="手机号已注册")

    # 确保至少有一种登录方式
    if not user_data.email and not user_data.phone:
        raise HTTPException(status_code=400, detail="邮箱和手机号至少需要填写一项")

    # 创建新用户，默认为个人版
    new_user = User(
        email=user_data.email,
        phone=user_data.phone,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        user_type="personal",
        subscription_tier="free",
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    sub = new_user.email or new_user.phone
    access_token = create_access_token(
        data={"sub": sub, "user_id": new_user.id, "user_type": new_user.user_type}
    )
    logger.info("用户注册成功: {}", sub)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    identifier = user_data.identifier

    # 判断是邮箱还是手机号登录
    if "@" in identifier:
        result = await db.execute(select(User).where(User.email == identifier))
        user = result.scalar_one_or_none()
        error_msg = "邮箱或密码错误"
    elif identifier.isdigit() and len(identifier) == 11 and identifier.startswith("1"):
        result = await db.execute(select(User).where(User.phone == identifier))
        user = result.scalar_one_or_none()
        error_msg = "手机号或密码错误"
    else:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱或手机号")

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    sub = user.email or user.phone
    access_token = create_access_token(
        data={"sub": sub, "user_id": user.id, "user_type": user.user_type}
    )
    logger.info("用户登录成功: {} (user_type={})", sub, user.user_type)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        phone=current_user.phone,
        user_type=current_user.user_type,
        subscription_tier=current_user.subscription_tier,
        subscription_expiry=current_user.subscription_expiry,
        trial_started_at=current_user.trial_started_at,
        enterprise_brand=current_user.enterprise_brand,
        created_at=current_user.created_at,
    )


@router.post("/switch-version")
async def switch_version(
    req: SwitchVersionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    DEMO功能：在前端切换当前展示的版本（个人版/企业版）。
    实际产品中个人升级企业需要提交证明材料，此处为演示简化。
    """
    if req.user_type not in ("personal", "enterprise"):
        raise HTTPException(status_code=400, detail="无效的版本类型，可选 personal 或 enterprise")

    current_user.user_type = req.user_type
    if req.user_type == "enterprise" and not current_user.trial_started_at:
        # 首次切换到企业版时，自动开始试用
        from datetime import datetime, timedelta
        current_user.trial_started_at = datetime.utcnow()
        current_user.subscription_tier = "enterprise"
        current_user.subscription_expiry = datetime.utcnow() + timedelta(days=30)

    await db.commit()
    await db.refresh(current_user)

    logger.info("用户 {} 切换版本到 {}", current_user.username, req.user_type)
    return {
        "message": f"已切换到{'企业版' if req.user_type == 'enterprise' else '个人版'}",
        "user_type": current_user.user_type,
        "subscription_tier": current_user.subscription_tier,
        "subscription_expiry": current_user.subscription_expiry,
    }
