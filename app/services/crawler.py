"""
爬虫服务模块 - 用于抓取各平台视频信息

⚠️ 注意：当前为模拟数据实现
TODO: 实现真实爬虫逻辑
- 小红书: 需要登录态或使用第三方API
- 抖音: 建议使用官方API或第三方SDK
- B站: 可使用 requests + BeautifulSoup 抓取公开信息
- 微博: 视频号内容可通过网页抓取
"""

import re
import random
from typing import Optional
from urllib.parse import urlparse

from app.schemas.monitor import VideoInfo


# 平台域名映射
PLATFORM_DOMAINS = {
    "xiaohongshu": ["xiaohongshu.com", "xhslink.com"],
    "douyin": ["douyin.com", "iesdouyin.com", "v.douyin.com"],
    "bilibili": ["bilibili.com", "b23.tv"],
}


def _detect_platform(url: str) -> Optional[str]:
    """根据URL检测平台"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        for platform, domains in PLATFORM_DOMAINS.items():
            if any(d in domain for d in domains):
                return platform
        return None
    except Exception:
        return None


def _extract_video_id(url: str, platform: str) -> str:
    """从URL中提取视频ID"""
    try:
        parsed = urlparse(url)
        path = parsed.path
        
        if platform == "xiaohongshu":
            # 小红书: /explore/xxx 或 /discovery/item/xxx
            match = re.search(r'/explore/([a-zA-Z0-9]+)', path)
            if match:
                return match.group(1)
            match = re.search(r'/discovery/item/([a-zA-Z0-9]+)', path)
            if match:
                return match.group(1)
        
        elif platform == "douyin":
            # 抖音: /video/xxx 或直接是数字ID
            match = re.search(r'/video/(\d+)', path)
            if match:
                return match.group(1)
            # 短链接格式
            match = re.search(r'(\d{19,})', url)
            if match:
                return match.group(1)
        
        elif platform == "bilibili":
            # B站: /video/BVxxx 或 /BVxxx
            match = re.search(r'/video/(BV[\w]+|av\d+)', path)
            if match:
                return match.group(1)
        
        return path.split('/')[-1] if path else "unknown"
    except Exception:
        return "unknown"


def _generate_mock_data(platform: str, video_id: str) -> VideoInfo:
    """生成模拟数据（优先使用预设Demo数据，降级为随机）"""
    from app.services.demo_data import get_crawler_preset

    # 平台名映射
    platform_name_map = {
        "xiaohongshu": "小红书", "douyin": "抖音",
        "bilibili": "B站", "weibo": "微博", "zhihu": "知乎",
    }
    cn_name = platform_name_map.get(platform, platform)

    try:
        preset = get_crawler_preset(cn_name, "")
        title = preset.get("title", f"关于XX的讨论")
        like_count = preset.get("like_count", 10000)
        comment_count = preset.get("comment_count", 3000)
        comments_sample = preset.get("comments_sample", [])
        comments = [c.get("content", "") for c in comments_sample]
    except Exception:
        title = f"关于品牌的最新讨论"
        like_count = 85000
        comment_count = 12000
        comments = ["期待更多细节", "观望中，再看看", "已入手，体验不错"]

    return VideoInfo(
        platform=platform,
        video_id=video_id,
        title=title,
        cover_url=f"https://picsum.photos/seed/{video_id}/400/300",
        like_count=like_count,
        comment_count=comment_count,
        comments=comments
    )


async def fetch_video_info(url: str) -> VideoInfo:
    """
    获取视频信息（包括评论）
    
    ⚠️ 当前为模拟实现，返回假数据
    TODO: 实现真实爬虫逻辑
    
    Args:
        url: 视频链接
        
    Returns:
        VideoInfo: 包含视频信息和评论列表
    """
    # 1. 检测平台
    platform = _detect_platform(url)
    if not platform:
        # 默认返回小红书模拟数据
        platform = "xiaohongshu"
    
    # 2. 提取视频ID
    video_id = _extract_video_id(url, platform)
    
    # 3. 模拟网络延迟（实际爬虫也需要）
    import asyncio
    await asyncio.sleep(random.uniform(0.5, 1.5))
    
    # 4. 返回模拟数据
    # TODO: 在此处替换为真实爬虫逻辑
    # 
    # 真实实现示例（以B站为例）：
    # if platform == "bilibili":
    #     return await _fetch_bilibili(url, video_id)
    # elif platform == "douyin":
    #     return await _fetch_douyin(url, video_id)
    # elif platform == "xiaohongshu":
    #     return await _fetch_xiaohongshu(url, video_id)
    
    return _generate_mock_data(platform, video_id)


async def fetch_comments_only(url: str, limit: int = 100) -> list:
    """
    仅获取评论列表（用于后续扩展）
    
    Args:
        url: 视频链接
        limit: 最大评论数
        
    Returns:
        评论列表
    """
    video_info = await fetch_video_info(url)
    return video_info.comments[:limit]
