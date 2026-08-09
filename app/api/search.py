"""
搜索 API 路由
对接秘塔 /api/v1/search，提供统一格式的搜索接口。
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.metaso_client import search as metaso_search
from app.utils.logger import logger

router = APIRouter(prefix="/api/search", tags=["搜索"])


# ============================================================
# 请求 / 响应模型
# ============================================================

class SearchRequest(BaseModel):
    q: str = Field(..., description="搜索问题或查询文本", min_length=1, max_length=5000)
    scope: str = Field("all", description="搜索范围，默认 all")
    size: int = Field(10, description="返回条数，默认 10", ge=1, le=50)
    include_summary: bool = Field(True, description="是否包含摘要，默认 true")


class SearchResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None


# ============================================================
# 路由
# ============================================================

@router.post("", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    """
    调用秘塔 /api/v1/search 进行语义搜索。

    请求体：
    - q:               查询文本（必填）
    - scope:           搜索范围，默认 "all"
    - size:            返回条数，默认 10
    - include_summary: 是否包含摘要，默认 true

    返回：
    - success:  是否成功
    - message:  提示信息
    - data:     { text, references }
    - error:    错误信息（成功时为 null）
    """
    logger.info(
        "搜索API请求: q={}, scope={}, size={}, include_summary={}",
        request.q[:100],
        request.scope,
        request.size,
        request.include_summary,
    )

    result = await metaso_search(
        q=request.q,
        scope=request.scope,
        size=request.size,
        include_summary=request.include_summary,
    )

    if result["success"]:
        return SearchResponse(
            success=True,
            message="搜索成功",
            data={
                "text": result["text"],
                "references": result["references"],
            },
            error=None,
        )
    else:
        return SearchResponse(
            success=False,
            message="搜索失败",
            data=None,
            error=result["error"],
        )
