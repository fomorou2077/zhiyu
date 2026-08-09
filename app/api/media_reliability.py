"""
媒体可靠性分级 API 路由
"""

import re
from typing import Optional, Tuple, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.media_reliability import (
    get_rating_cached_or_bailian,
    batch_get_ratings,
)
from app.utils.logger import logger

router = APIRouter(prefix="/media", tags=["媒体可靠性"])


class MediaCheckRequest(BaseModel):
    """媒体检查请求"""
    input: str = Field(..., description="媒体名称、URL或域名")
    force_refresh: bool = Field(False, description="是否强制刷新缓存")


class MediaCheckResponse(BaseModel):
    """媒体检查响应"""
    media_name: str = Field(..., description="媒体名称")
    domain: Optional[str] = Field(None, description="媒体域名")
    rating: str = Field(..., description="评级结果：可信/中等/存疑/虚假")
    reason: str = Field(..., description="评级理由")
    evidence: list = Field(default_factory=list, description="证据列表")
    source: str = Field(..., description="数据来源")
    cached: bool = Field(False, description="是否来自缓存")


class BatchCheckRequest(BaseModel):
    """批量检查请求"""
    items: List[dict] = Field(
        default_factory=list,
        description="媒体列表，格式：[{'name': '媒体名', 'domain': '域名'}, ...]"
    )


@router.post("/check", response_model=MediaCheckResponse)
async def check_media(
    request: MediaCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    检查媒体可靠性

    输入可以是：
    - 完整URL（如 https://news.example.com/article/123）
    - 域名（如 news.example.com 或 example.com）
    - 媒体名称（如 "新浪新闻"、"腾讯新闻"）
    """
    input_str = request.input.strip()

    if not input_str:
        raise HTTPException(status_code=400, detail="输入不能为空")

    # 解析输入
    media_name, domain = _parse_media_input(input_str)

    if not media_name:
        raise HTTPException(status_code=400, detail="无法识别媒体信息")

    logger.info("开始检查媒体: name={}, domain={}", media_name, domain)

    try:
        # 获取评级
        result = await get_rating_cached_or_bailian(
            media_name=media_name,
            domain=domain,
            db=db,
            force_refresh=request.force_refresh
        )

        return MediaCheckResponse(
            media_name=media_name,
            domain=domain,
            rating=result.get("rating", "存疑"),
            reason=result.get("reason", ""),
            evidence=result.get("evidence", []),
            source=result.get("source", "未知"),
            cached=result.get("cached", False)
        )

    except Exception as e:
        logger.exception("媒体检查失败: {}", e)
        raise HTTPException(
            status_code=500,
            detail=f"媒体检查失败: {str(e)}"
        )


@router.post("/batch-check")
async def batch_check_media(
    request: BatchCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    批量检查多个媒体的可靠性
    """
    if not request.items:
        raise HTTPException(status_code=400, detail="媒体列表不能为空")

    if len(request.items) > 20:
        raise HTTPException(status_code=400, detail="单次最多支持20个媒体")

    logger.info("批量检查 {} 个媒体", len(request.items))

    try:
        results = await batch_get_ratings(db, request.items)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.exception("批量检查失败: {}", e)
        raise HTTPException(
            status_code=500,
            detail=f"批量检查失败: {str(e)}"
        )


@router.get("/cache/{domain}")
async def get_cached_rating(
    domain: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取媒体域名的缓存评级
    """
    from app.services.media_reliability import get_rating_cached

    cached = await get_rating_cached(db, domain)

    if cached:
        return cached

    return {"message": "暂无缓存"}


@router.delete("/cache/{domain}")
async def delete_cached_rating(
    domain: str,
    db: AsyncSession = Depends(get_db)
):
    """
    删除媒体域名的缓存记录
    """
    from app.models.media_reliability import MediaReliability
    from sqlalchemy import delete

    try:
        await db.execute(
            delete(MediaReliability).where(MediaReliability.domain == domain)
        )
        await db.commit()
        return {"message": "缓存已删除"}
    except Exception as e:
        logger.exception("删除缓存失败: {}", e)
        raise HTTPException(
            status_code=500,
            detail=f"删除缓存失败: {str(e)}"
        )


def _parse_media_input(input_str: str) -> Tuple[str, Optional[str]]:
    """
    解析用户输入，提取媒体名称和域名

    Returns:
        (media_name, domain)
    """
    input_str = input_str.strip()

    # 如果是URL
    if input_str.startswith(("http://", "https://")):
        domain = _extract_domain(input_str)
        media_name = _infer_media_name(domain) if domain else input_str
        return media_name, domain

    # 如果只是域名（带www或点号）
    if _looks_like_domain(input_str):
        domain = _normalize_domain(input_str)
        media_name = _infer_media_name(domain)
        return media_name, domain

    # 纯文本，当作媒体名称处理
    return input_str, None


def _extract_domain(url: str) -> Optional[str]:
    """从URL提取域名"""
    try:
        # 移除协议
        url = re.sub(r'^https?://', '', url)
        # 移除路径、查询参数等
        domain = url.split('/')[0]
        # 移除端口号
        domain = domain.split(':')[0]
        # 移除 www.
        domain = re.sub(r'^www\.', '', domain)
        return domain if domain else None
    except Exception:
        return None


def _normalize_domain(domain: str) -> str:
    """规范化域名"""
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.split('/')[0]
    domain = domain.split(':')[0]
    domain = re.sub(r'^www\.', '', domain)
    return domain


def _looks_like_domain(input_str: str) -> bool:
    """判断输入是否像域名"""
    return bool(
        re.match(r'^[\w-]+(\.[\w-]+)+$', input_str) or
        input_str.startswith('www.') or
        '.' in input_str
    )


def _infer_media_name(domain: str) -> str:
    """从域名推断媒体名称"""
    if not domain:
        return ""

    domain_lower = domain.lower()

    MEDIA_NAMES = {
        "sina.com.cn": "新浪网",
        "sohu.com": "搜狐网",
        "163.com": "网易",
        "qq.com": "腾讯网",
        "ifeng.com": "凤凰网",
        "people.com.cn": "人民网",
        "xinhuanet.com": "新华网",
        "cctv.com": "央视网",
        "baidu.com": "百度",
        "weibo.com": "微博",
        "zhihu.com": "知乎",
        "bilibili.com": "哔哩哔哩",
        "douyin.com": "抖音",
        "kuaishou.com": "快手",
        "toutiao.com": "今日头条",
        "thepaper.cn": "澎湃新闻",
        "jiemian.com": "界面新闻",
        "guancha.cn": "观察者网",
        "caixin.com": "财新",
        " Guancha": "观察者网",
        "rfi.fr": "法国国际广播电台",
        "bbc.com": "BBC",
        "voa.com": "美国之音",
        "dw.com": "德国之声",
        "Radio Free Asia": "自由亚洲电台",
        "epochtimes.com": "大纪元",
        "ntdtv.com": "新唐人电视台",
        "clearwisdom.net": "明慧网",
    }

    for key, name in MEDIA_NAMES.items():
        if key in domain_lower:
            return name

    # 尝试从域名第一部分提取
    parts = domain.split('.')
    if parts:
        return parts[0].capitalize()

    return domain
