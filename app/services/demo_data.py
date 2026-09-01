"""
Demo预设数据模块
为仪表盘、爬虫等功能提供多套预设的逼真Demo数据
正式接入真实API后替换此模块即可
"""
from datetime import datetime, timedelta


# ============================================================
# 仪表盘预设（5套品牌场景）
# ============================================================

DASHBOARD_PRESETS = {
    "default": {
        "brand": "知舆Demo品牌",
        "industry": "互联网科技",
        "heat_trend": {
            "labels": [(datetime.now() - timedelta(hours=h)).strftime("%H:00") for h in range(23, -1, -1)],
            "values": [35, 42, 38, 45, 55, 62, 58, 70, 85, 92, 88, 95, 100, 87, 72, 65, 60, 55, 68, 75, 80, 72, 58, 45],
        },
        "sentiment": {"positive": 62, "neutral": 25, "negative": 13},
        "keyword_cloud": [
            {"text": "新品发布", "weight": 85}, {"text": "用户体验", "weight": 72},
            {"text": "性价比", "weight": 65}, {"text": "创新", "weight": 58},
            {"text": "服务", "weight": 48}, {"text": "好评", "weight": 42},
            {"text": "期待", "weight": 40}, {"text": "对比竞品", "weight": 35},
        ],
        "recent_mentions": [
            {"platform": "微博", "title": "这款新品真的超出预期了", "sentiment": "positive", "time": "10分钟前", "url": "#"},
            {"platform": "抖音", "title": "开箱视频火了！3小时50万播放", "sentiment": "positive", "time": "25分钟前", "url": "#"},
            {"platform": "小红书", "title": "真实使用体验分享", "sentiment": "positive", "time": "45分钟前", "url": "#"},
            {"platform": "B站", "title": "深度测评：优缺点都很明显", "sentiment": "neutral", "time": "1小时前", "url": "#"},
            {"platform": "知乎", "title": "如何评价XX品牌的新品策略？", "sentiment": "neutral", "time": "2小时前", "url": "#"},
            {"platform": "微博", "title": "客服响应太慢了，等了三天", "sentiment": "negative", "time": "3小时前", "url": "#"},
        ],
        "alert_count": 1,
        "monitored_platforms": ["微博", "抖音", "小红书", "B站", "知乎"],
    },

    "crisis": {
        "brand": "品牌危机模拟",
        "industry": "消费品",
        "heat_trend": {
            "labels": [(datetime.now() - timedelta(hours=h)).strftime("%H:00") for h in range(23, -1, -1)],
            "values": [10, 12, 8, 15, 20, 45, 120, 250, 380, 420, 390, 350, 280, 200, 160, 130, 110, 95, 85, 78, 70, 65, 55, 48],
        },
        "sentiment": {"positive": 18, "neutral": 22, "negative": 60},
        "keyword_cloud": [
            {"text": "维权", "weight": 95}, {"text": "投诉", "weight": 88},
            {"text": "质量问题", "weight": 82}, {"text": "退款", "weight": 75},
            {"text": "欺骗", "weight": 68}, {"text": "曝光", "weight": 60},
            {"text": "道歉", "weight": 55}, {"text": "赔偿", "weight": 48},
        ],
        "recent_mentions": [
            {"platform": "微博", "title": "维权博文引发热议，转发超10万", "sentiment": "negative", "time": "5分钟前", "url": "#"},
            {"platform": "抖音", "title": "消费者控诉视频登上热门", "sentiment": "negative", "time": "15分钟前", "url": "#"},
            {"platform": "小红书", "title": "多人发帖曝光同样问题", "sentiment": "negative", "time": "30分钟前", "url": "#"},
            {"platform": "知乎", "title": "如何看待XX品牌最新争议？", "sentiment": "negative", "time": "1小时前", "url": "#"},
            {"platform": "微博", "title": "官方尚未回应，网友催更", "sentiment": "neutral", "time": "1小时前", "url": "#"},
            {"platform": "B站", "title": "UP主深度分析本次事件来龙去脉", "sentiment": "neutral", "time": "2小时前", "url": "#"},
        ],
        "alert_count": 5,
        "monitored_platforms": ["微博", "抖音", "小红书", "B站", "知乎", "今日头条"],
    },

    "new_product": {
        "brand": "新品上市",
        "industry": "消费电子",
        "heat_trend": {
            "labels": [(datetime.now() - timedelta(hours=h)).strftime("%H:00") for h in range(23, -1, -1)],
            "values": [80, 75, 70, 68, 72, 85, 120, 180, 250, 300, 350, 420, 480, 450, 380, 320, 280, 260, 240, 220, 200, 180, 150, 120],
        },
        "sentiment": {"positive": 72, "neutral": 20, "negative": 8},
        "keyword_cloud": [
            {"text": "首发", "weight": 90}, {"text": "黑科技", "weight": 82},
            {"text": "抢购", "weight": 75}, {"text": "测评", "weight": 70},
            {"text": "价格", "weight": 60}, {"text": "外观", "weight": 55},
            {"text": "对比", "weight": 45}, {"text": "预订", "weight": 40},
        ],
        "recent_mentions": [
            {"platform": "微博", "title": "发布会直播观看人数破500万", "sentiment": "positive", "time": "刚刚", "url": "#"},
            {"platform": "抖音", "title": "真机上手体验，流畅度惊艳", "sentiment": "positive", "time": "10分钟前", "url": "#"},
            {"platform": "B站", "title": "深度拆解：内部做工到底怎么样", "sentiment": "positive", "time": "30分钟前", "url": "#"},
            {"platform": "小红书", "title": "开箱美图，颜值真的很能打", "sentiment": "positive", "time": "1小时前", "url": "#"},
            {"platform": "知乎", "title": "XX新品相比竞品有什么优势？", "sentiment": "neutral", "time": "2小时前", "url": "#"},
            {"platform": "微博", "title": "价格略高，再观望一下", "sentiment": "neutral", "time": "3小时前", "url": "#"},
        ],
        "alert_count": 0,
        "monitored_platforms": ["微博", "抖音", "小红书", "B站", "知乎", "快手"],
    },

    "competitor": {
        "brand": "竞品动态",
        "industry": "餐饮连锁",
        "heat_trend": {
            "labels": [(datetime.now() - timedelta(hours=h)).strftime("%H:00") for h in range(23, -1, -1)],
            "values": [40, 38, 42, 45, 48, 52, 55, 58, 60, 62, 58, 55, 52, 50, 48, 46, 44, 42, 45, 48, 50, 48, 45, 42],
        },
        "sentiment": {"positive": 45, "neutral": 35, "negative": 20},
        "keyword_cloud": [
            {"text": "联名", "weight": 78}, {"text": "新品", "weight": 65},
            {"text": "排队", "weight": 55}, {"text": "口味", "weight": 50},
            {"text": "环境", "weight": 42}, {"text": "价格", "weight": 38},
            {"text": "服务", "weight": 35}, {"text": "外卖", "weight": 30},
        ],
        "recent_mentions": [
            {"platform": "小红书", "title": "新出的联名款也太可爱了吧", "sentiment": "positive", "time": "20分钟前", "url": "#"},
            {"platform": "抖音", "title": "探店视频3小时20万赞", "sentiment": "positive", "time": "1小时前", "url": "#"},
            {"platform": "微博", "title": "XX品牌的营销做得真好", "sentiment": "positive", "time": "2小时前", "url": "#"},
            {"platform": "知乎", "title": "如何评价XX品牌最近扩张速度", "sentiment": "neutral", "time": "3小时前", "url": "#"},
            {"platform": "大众点评", "title": "新店排队太久，建议避开高峰期", "sentiment": "negative", "time": "4小时前", "url": "#"},
        ],
        "alert_count": 0,
        "monitored_platforms": ["微博", "抖音", "小红书", "知乎", "大众点评"],
    },

    "industry_trend": {
        "brand": "行业趋势洞察",
        "industry": "新能源汽车",
        "heat_trend": {
            "labels": [(datetime.now() - timedelta(hours=h)).strftime("%H:00") for h in range(23, -1, -1)],
            "values": [55, 58, 62, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 108, 102, 95, 88, 82, 78, 75, 72, 68, 62, 58],
        },
        "sentiment": {"positive": 55, "neutral": 30, "negative": 15},
        "keyword_cloud": [
            {"text": "智能驾驶", "weight": 88}, {"text": "续航", "weight": 75},
            {"text": "充电", "weight": 68}, {"text": "价格战", "weight": 62},
            {"text": "政策", "weight": 55}, {"text": "补贴", "weight": 48},
            {"text": "电池", "weight": 42}, {"text": "OTA升级", "weight": 38},
        ],
        "recent_mentions": [
            {"platform": "微博", "title": "新能源汽车渗透率再创新高", "sentiment": "positive", "time": "30分钟前", "url": "#"},
            {"platform": "知乎", "title": "2026年下半年新能源市场展望", "sentiment": "neutral", "time": "1小时前", "url": "#"},
            {"platform": "抖音", "title": "行业大V分析价格战走向", "sentiment": "neutral", "time": "2小时前", "url": "#"},
            {"platform": "B站", "title": "深度解读最新补贴政策", "sentiment": "positive", "time": "3小时前", "url": "#"},
        ],
        "alert_count": 1,
        "monitored_platforms": ["微博", "抖音", "知乎", "B站", "今日头条"],
    },
}


# ============================================================
# 爬虫预设（按平台 + 关键词返回不同数据）
# ============================================================

CRAWLER_PRESETS = {
    ("微博", "default"): {
        "platform": "微博",
        "video_id": "weibo_4938210000000000",
        "title": "行业热议：品牌发展新趋势引发广泛关注",
        "cover_url": "",
        "like_count": 12500,
        "comment_count": 3420,
        "share_count": 5600,
        "comments_sample": [
            {"user": "用户A", "content": "说得有道理，确实应该关注这个问题", "sentiment": "positive"},
            {"user": "用户B", "content": "希望品牌方能重视用户体验", "sentiment": "neutral"},
            {"user": "用户C", "content": "太失望了，等了这么久就这？", "sentiment": "negative"},
        ],
    },
    ("抖音", "default"): {
        "platform": "抖音",
        "video_id": "douyin_7382910000000000",
        "title": "一分钟带你了解最新动态 #热点 #科普",
        "cover_url": "",
        "like_count": 89500,
        "comment_count": 12400,
        "share_count": 28000,
        "comments_sample": [
            {"user": "抖友001", "content": "涨知识了！原来是这样", "sentiment": "positive"},
            {"user": "抖友002", "content": "这不就是换了个壳吗...", "sentiment": "negative"},
            {"user": "抖友003", "content": "价格还行，可以考虑入手", "sentiment": "positive"},
        ],
    },
    ("小红书", "default"): {
        "platform": "小红书",
        "video_id": "xhs_5928100000000000",
        "title": "真实使用体验｜入手一个月后的感受",
        "cover_url": "",
        "like_count": 34200,
        "comment_count": 8900,
        "share_count": 12000,
        "comments_sample": [
            {"user": "小红薯A", "content": "种草了！马上去下单", "sentiment": "positive"},
            {"user": "小红薯B", "content": "颜色真的好好看啊啊啊", "sentiment": "positive"},
            {"user": "小红薯C", "content": "用了两周就坏了，差评", "sentiment": "negative"},
        ],
    },
    ("B站", "default"): {
        "platform": "B站",
        "video_id": "bilibili_BV1xx411c7xx",
        "title": "深度测评：到底值不值得买？万字长文解析",
        "cover_url": "",
        "like_count": 56700,
        "comment_count": 15600,
        "share_count": 8900,
        "comments_sample": [
            {"user": "B站用户A", "content": "UP主讲得太详细了，三连支持", "sentiment": "positive"},
            {"user": "B站用户B", "content": "理性分析，优缺点都说到了", "sentiment": "neutral"},
            {"user": "B站用户C", "content": "恰饭视频，鉴定完毕", "sentiment": "negative"},
        ],
    },
    ("知乎", "default"): {
        "platform": "知乎",
        "video_id": "zhihu_9982100000000000",
        "title": "如何看待XX事件的持续发酵？业内人士深度分析",
        "cover_url": "",
        "like_count": 28000,
        "comment_count": 9500,
        "share_count": 4200,
        "comments_sample": [
            {"user": "知乎用户A", "content": "作为从业者，补充一些背景信息...", "sentiment": "neutral"},
            {"user": "知乎用户B", "content": "高赞回答都太片面了，我来补充几点", "sentiment": "neutral"},
            {"user": "知乎用户C", "content": "数据翔实，逻辑清晰，这才是知乎该有的回答", "sentiment": "positive"},
        ],
    },
}


def get_dashboard_preset(brand_name: str = "") -> dict:
    """根据品牌名匹配仪表盘预设场景"""
    name = (brand_name or "").lower()
    if any(w in name for w in ["危机", "投诉", "维权", "曝光", "crisis"]):
        return DASHBOARD_PRESETS["crisis"]
    if any(w in name for w in ["新品", "发布", "上市", "首发", "new"]):
        return DASHBOARD_PRESETS["new_product"]
    if any(w in name for w in ["竞品", "对手", "竞争", "competitor"]):
        return DASHBOARD_PRESETS["competitor"]
    if any(w in name for w in ["汽车", "新能源", "行业", "趋势", "industry"]):
        return DASHBOARD_PRESETS["industry_trend"]
    return DASHBOARD_PRESETS["default"]


def get_crawler_preset(platform: str, keyword: str = "") -> dict:
    """根据平台和关键词匹配爬虫预设数据"""
    key = (platform, "default")
    preset = CRAWLER_PRESETS.get(key, CRAWLER_PRESETS.get(("微博", "default"), {}))
    result = dict(preset)  # 浅拷贝
    if keyword:
        result["title"] = f"关于「{keyword}」的相关讨论"
    return result
