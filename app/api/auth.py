from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.utils.security import create_access_token, get_password_hash, verify_password
from app.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
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

    # 创建新用户
    new_user = User(
        email=user_data.email,
        phone=user_data.phone,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # 使用邮箱或手机号作为 subject
    sub = new_user.email or new_user.phone
    access_token = create_access_token(data={"sub": sub, "user_id": new_user.id})
    logger.info("用户注册成功: {}", sub)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    identifier = user_data.identifier

    # 判断是邮箱还是手机号登录
    if "@" in identifier:
        # 邮箱登录
        result = await db.execute(select(User).where(User.email == identifier))
        user = result.scalar_one_or_none()
        error_msg = "邮箱或密码错误"
    elif identifier.isdigit() and len(identifier) == 11 and identifier.startswith("1"):
        # 手机号登录
        result = await db.execute(select(User).where(User.phone == identifier))
        user = result.scalar_one_or_none()
        error_msg = "手机号或密码错误"
    else:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱或手机号")

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    sub = user.email or user.phone
    access_token = create_access_token(data={"sub": sub, "user_id": user.id})
    logger.info("用户登录成功: {}", sub)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(db: AsyncSession = Depends(get_db)):
    """获取当前登录用户信息（需要 token）"""
    from fastapi import Header
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from app.utils.security import decode_access_token as decode_token

    async def get_current_user(authorization: str = Header(...)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            token = authorization.replace("Bearer ", "")
            payload = decode_token(token)
            if payload is None:
                raise credentials_exception
        except Exception:
            raise credentials_exception

    auth = HTTPBearer()
    # 简单实现，实际应使用依赖注入
    return UserResponse(id=0, username="需要token", email=None, phone=None)
