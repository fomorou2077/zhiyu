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
    """生成模拟数据（用于测试和演示）"""
    
    # 各平台的模拟标题
    mock_titles = {
        "xiaohongshu": [
            "这款护肤神器真的绝了！用了皮肤嫩到发光",
            "周末探店 | 这家咖啡馆氛围感满分",
            "穿搭分享 | 简约风格也能穿出高级感",
            "美食推荐 | 隐藏在巷子里的宝藏小店",
            "plog | 独居女孩的精致生活日常"
        ],
        "douyin": [
            "这个技巧太实用了，建议收藏！",
            "原来这么简单，后悔现在才知道",
            "看完这个视频，我决定要改变了",
            "不得不说的内幕，看完别惊讶",
            "生活小妙招，省钱又实用"
        ],
        "bilibili": [
            "【必看】这个知识点考试一定会考",
            "深度解析 | 为什么这件事件引发全网热议",
            "Vlog | 我的留学生活plog",
            "数码测评 | 这款产品到底值不值得买",
            "教程 | 从零开始学XX的正确姿势"
        ]
    }
    
    # 根据平台生成模拟评论
    mock_comments = {
        "xiaohongshu": [
            "真的太好用了！回购好几次了",
            "感谢博主推荐，已入手",
            "这个价格太划算了",
            "有点心动，但是怕踩雷",
            "已买，等我反馈效果",
            "博主皮肤好好，用的什么护肤品",
            "假的吧，哪有这么好用",
            "我觉得一般般，没有说的那么好",
            "求链接，求购买方式",
            "周末去探店打卡",
            "氛围感满满，爱了爱了",
            "这个穿搭技巧学到了",
            "太贵了，承受不起",
            "理性消费，不盲目跟风",
            "支持博主，质量应该没问题"
        ],
        "douyin": [
            "这个方法太棒了，终于解决了",
            "学到了学到了，谢谢分享",
            "我就说怎么一直不行呢",
            "早知道这个方法就好了",
            "不会吧，真的假的？",
            "评论区都在说好用",
            "买了，用了确实有效",
            "智商税吧，千万别买",
            "支持主播，质量有保障",
            "已经推荐给朋友了",
            "这内容有点夸张了吧",
            "说实话，一般般",
            "等等我再考虑考虑",
            "冲冲冲，已下单",
            "等优惠再买"
        ],
        "bilibili": [
            "这期视频干货满满，点赞投币收藏",
            "终于有人把这件事说清楚了",
            "弹幕：前排围观",
            "这知识点太硬核了",
            "说实话，有点失望",
            "支持up主，加油更新",
            "这内容有点水了吧",
            "纯路人，这视频质量不错",
            "建议大家理性看待",
            "终于更新了，等了好久",
            "这期视频有点翻车",
            "内容一般，但up主很努力",
            "质量不错，会持续关注",
            "说实话，有点看不懂",
            "这期比上期好多了"
        ]
    }
    
    # 情绪关键词（用于模拟分析）
    positive_keywords = ["太棒了", "好用了", "支持", "推荐", "学到了", "干货", "满分", "喜欢", "爱了", "收藏", "点赞", "回购", "划算"]
    negative_keywords = ["假的", "智商税", "失望", "翻车", "一般般", "太贵", "夸张", "踩雷", "水", "理性", "考虑", "观望"]
    neutral_keywords = ["等等", "已买", "求链接", "围观", "路人", "关注"]
    
    titles = mock_titles.get(platform, mock_titles["xiaohongshu"])
    comments = mock_comments.get(platform, mock_comments["xiaohongshu"])
    
    # 随机选择标题
    title = random.choice(titles)
    
    # 随机生成点赞和评论数
    like_count = random.randint(1000, 500000)
    comment_count = random.randint(50, 5000)
    
    # 随机选择部分评论
    selected_comments = random.sample(comments, min(len(comments), random.randint(10, 15)))
    
    return VideoInfo(
        platform=platform,
        video_id=video_id,
        title=title,
        cover_url=f"https://picsum.photos/seed/{video_id}/400/300",
        like_count=like_count,
        comment_count=comment_count,
        comments=selected_comments
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
