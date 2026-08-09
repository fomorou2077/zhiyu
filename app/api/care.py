from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.services.care_service import check_and_generate_care
from app.utils.logger import logger
from app.utils.security import decode_access_token as decode_token

router = APIRouter(prefix="/care", tags=["care"])


def get_user_id_from_header(authorization: str) -> int:
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


@router.get("/check")
async def check_care(
    authorization: str = Depends(lambda x: x.headers.get("authorization", "")),
    db: AsyncSession = Depends(get_db)
):
    """
    检查是否有新的关怀内容。
    前端在用户登录后或每日首次访问时调用。
    """
    try:
        user_id = get_user_id_from_header(authorization)
    except HTTPException:
        # 未登录用户不返回关怀
        return {"has_care": False, "care": None}

    care = await check_and_generate_care(user_id, db)

    if care:
        return {
            "has_care": True,
            "care": care
        }
    else:
        return {
            "has_care": False,
            "care": None
        }
