from typing import Optional

from app.services.hotspot_service import fetch_hotspots
from app.utils.logger import logger


async def get_today_hotspots() -> list:
    """
    获取今日热点推送列表。
    从热点服务获取全部热点，取前3条，格式化为简短通知。
    """
    try:
        hotspots = await fetch_hotspots(platform="all", limit=10)

        notifications = []
        for item in hotspots[:3]:
            title = item.get("title", "")[:30]
            platform = item.get("platform", "")
            heat = item.get("heat", 0)

            description = f"平台: {platform} | 热度: {heat}"

            notifications.append({
                "title": title,
                "description": description,
                "url": item.get("url", ""),
                "heat": heat
            })

        return notifications

    except Exception as e:
        logger.warning("获取热点通知失败: {}", e)
        return []


def should_show_notification(notifications_enabled: bool, last_shown_date: Optional[str]) -> bool:
    """
    判断今天是否应该显示推送通知。

    Args:
        notifications_enabled: 用户是否开启了推送开关
        last_shown_date: 上次显示推送的日期（YYYY-MM-DD格式）

    Returns:
        bool: 是否应该显示
    """
    if not notifications_enabled:
        return False

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    # 如果今天已经显示过，不再显示
    if last_shown_date == today:
        return False

    return True
