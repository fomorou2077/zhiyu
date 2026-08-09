"""
热点数据服务 - 获取微博、抖音、B站等平台热点话题
"""

import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional

from app.utils.logger import logger

# 模拟热点数据（后续可替换为真实爬虫或API）
MOCK_HOTSPOTS: Dict[str, List[Dict]] = {
    "weibo": [
        {"title": "热搜第一：某明星新剧开播引发热议", "heat": 12567890, "url": "https://weibo.com/xxx", "category": "娱乐"},
        {"title": "北京今日气温突破历史极值", "heat": 8923456, "url": "https://weibo.com/yyy", "category": "社会"},
        {"title": "苹果发布会官宣新机引期待", "heat": 7654321, "url": "https://weibo.com/zzz", "category": "科技"},
        {"title": "全国多地迎来大幅降温", "heat": 5432109, "url": "https://weibo.com/aaa", "category": "社会"},
        {"title": "某地高考分数线公布引关注", "heat": 4321098, "url": "https://weibo.com/bbb", "category": "教育"},
        {"title": "端午假期旅游数据创新高", "heat": 3210987, "url": "https://weibo.com/ccc", "category": "旅游"},
        {"title": "某电商平台推出新优惠活动", "heat": 2109876, "url": "https://weibo.com/ddd", "category": "商业"},
        {"title": "全国交通安全日宣传活动", "heat": 1987654, "url": "https://weibo.com/eee", "category": "公益"},
    ],
    "douyin": [
        {"title": "挑战全网最火舞蹈来了", "heat": 2345678, "url": "https://douyin.com/video/xxx", "category": "娱乐"},
        {"title": "探店博主揭秘网红餐厅", "heat": 1987654, "url": "https://douyin.com/video/yyy", "category": "生活"},
        {"title": "手把手教你做家常菜", "heat": 1765432, "url": "https://douyin.com/video/zzz", "category": "美食"},
        {"title": "萌宠日常太治愈了", "heat": 1543210, "url": "https://douyin.com/video/aaa", "category": "萌宠"},
        {"title": "这波操作秀翻全场", "heat": 1321098, "url": "https://douyin.com/video/bbb", "category": "搞笑"},
        {"title": "穿搭博主推荐好物", "heat": 1109876, "url": "https://douyin.com/video/ccc", "category": "时尚"},
        {"title": "健身达人的日常训练", "heat": 987654, "url": "https://douyin.com/video/ddd", "category": "健身"},
        {"title": "旅行博主带你游遍全国", "heat": 876543, "url": "https://douyin.com/video/eee", "category": "旅行"},
    ],
    "bilibili": [
        {"title": "UP主硬核拆解最新手机", "heat": 345678, "url": "https://bilibili.com/video/xxx", "category": "科技"},
        {"title": "虚拟主播新衣回放收藏", "heat": 298765, "url": "https://bilibili.com/video/yyy", "category": "动漫"},
        {"title": "某游戏年度更新内容", "heat": 276543, "url": "https://bilibili.com/video/zzz", "category": "游戏"},
        {"title": "大学生期末复习日常", "heat": 254321, "url": "https://bilibili.com/video/aaa", "category": "生活"},
        {"title": "高分纪录片推荐", "heat": 232109, "url": "https://bilibili.com/video/bbb", "category": "纪录片"},
        {"title": "手工耿最新作品", "heat": 210987, "url": "https://bilibili.com/video/ccc", "category": "手工"},
        {"title": "某动画第一集发布", "heat": 198765, "url": "https://bilibili.com/video/ddd", "category": "动漫"},
        {"title": "音乐区翻唱神曲", "heat": 176543, "url": "https://bilibili.com/video/eee", "category": "音乐"},
    ],
}

# 平台中文名映射
PLATFORM_NAMES = {
    "weibo": "微博",
    "douyin": "抖音",
    "bilibili": "B站",
}


async def fetch_hotspots(
    platform: Optional[str] = None,
    limit: int = 20,
    with_category: bool = True
) -> List[Dict]:
    """
    获取热点数据

    Args:
        platform: 平台名称 (weibo/douyin/bilibili)，None 表示全部
        limit: 返回数量限制
        with_category: 是否返回分类信息

    Returns:
        热点列表，按热度降序排列
    """
    await asyncio.sleep(0.15)

    result = []

    if platform:
        platforms_to_fetch = [platform]
    else:
        platforms_to_fetch = list(MOCK_HOTSPOTS.keys())

    for plat in platforms_to_fetch:
        for idx, item in enumerate(MOCK_HOTSPOTS.get(plat, [])):
            # 为每次请求添加微小随机波动，模拟实时变化
            heat_with_noise = item["heat"] + random.randint(-5000, 5000)
            entry: Dict = {
                "platform": plat,
                "platform_name": PLATFORM_NAMES.get(plat, plat),
                "title": item["title"],
                "heat": max(0, heat_with_noise),
                "url": item["url"],
                "timestamp": datetime.now().isoformat(),
            }
            if with_category:
                entry["category"] = item.get("category", "综合")
            result.append(entry)

    # 按热度降序
    result.sort(key=lambda x: x["heat"], reverse=True)

    # 截取数量并添加排名
    result = result[:limit]
    for i, item in enumerate(result):
        item["rank"] = i + 1

    logger.info(
        "获取热点数据: platform={}, count={}", platform or "all", len(result)
    )
    return result


async def fetch_hotspots_by_category(
    category: str,
    limit: int = 10
) -> List[Dict]:
    """
    按分类获取热点

    Args:
        category: 分类名称
        limit: 返回数量

    Returns:
        该分类下的热点列表
    """
    all_hotspots = await fetch_hotspots(limit=100, with_category=True)

    filtered = [h for h in all_hotspots if h.get("category") == category]
    return filtered[:limit]
