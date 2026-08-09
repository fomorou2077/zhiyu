"""
热点数据 API 路由
"""

from typing import List, Optional

from fastapi import APIRouter, Query

from app.schemas.hotspot import HotspotResponse
from app.services.hotspot_service import (
    fetch_hotspots,
    fetch_hotspots_by_category,
)

router = APIRouter(prefix="/hotspot", tags=["热点"])


@router.get("/", response_model=List[HotspotResponse])
async def get_hotspots(
    platform: Optional[str] = Query(
        None,
        description="平台名称: weibo, douyin, bilibili（不填则返回全部）"
    ),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    category: Optional[str] = Query(None, description="按分类筛选"),
):
    """
    获取热点数据

    - **platform**: 平台名称（weibo/douyin/bilibili）
    - **limit**: 返回数量（默认20条，最多100条）
    - **category**: 按分类筛选（可选）
    """
    if category:
        return await fetch_hotspots_by_category(category, limit=limit)

    return await fetch_hotspots(platform=platform, limit=limit)


@router.get("/platforms")
async def get_available_platforms():
    """
    获取可用的平台列表
    """
    return {
        "platforms": [
            {"id": "weibo", "name": "微博", "icon": "fa-weibo"},
            {"id": "douyin", "name": "抖音", "icon": "fa-tiktok"},
            {"id": "bilibili", "name": "B站", "icon": "fa-bilibili"},
        ]
    }


@router.get("/categories")
async def get_categories():
    """
    获取热点分类列表
    """
    categories = set()
    for items in [
        item
        for platform_items in [
            v for v in [
                v for k, v in {
                    "weibo": [
                        {"category": "娱乐"},
                        {"category": "社会"},
                        {"category": "科技"},
                        {"category": "教育"},
                        {"category": "旅游"},
                        {"category": "商业"},
                        {"category": "公益"},
                    ],
                    "douyin": [
                        {"category": "娱乐"},
                        {"category": "生活"},
                        {"category": "美食"},
                        {"category": "萌宠"},
                        {"category": "搞笑"},
                        {"category": "时尚"},
                        {"category": "健身"},
                        {"category": "旅行"},
                    ],
                    "bilibili": [
                        {"category": "科技"},
                        {"category": "动漫"},
                        {"category": "游戏"},
                        {"category": "生活"},
                        {"category": "纪录片"},
                        {"category": "手工"},
                        {"category": "音乐"},
                    ],
                }.values()
            ]
            for v in platform_items
        ]
        for item in items.values()
    ]:
        categories.add(categories)

    return {
        "categories": list(
            {
                "娱乐",
                "社会",
                "科技",
                "教育",
                "旅游",
                "商业",
                "公益",
                "生活",
                "美食",
                "萌宠",
                "搞笑",
                "时尚",
                "健身",
                "动漫",
                "游戏",
                "纪录片",
                "手工",
                "音乐",
            }
        )
    }
