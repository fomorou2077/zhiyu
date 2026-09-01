from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.care_service import check_and_generate_care

router = APIRouter(prefix="/care", tags=["care"])


@router.get("/check")
async def check_care(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查是否有新的关怀内容"""
    care = await check_and_generate_care(current_user.id, db)
    if care:
        return {"has_care": True, "care": care}
    else:
        return {"has_care": False, "care": None}
