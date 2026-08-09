"""
媒体可靠性分级服务
调用百炼大模型联网搜索，对媒体进行评级分析。
"""

import json
import re
from datetime import date
from typing import Optional, Tuple, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_reliability import MediaReliability
from app.services.baichuan_service import chat_with_ai
from app.utils.logger import logger

# 缓存有效期（天）
CACHE_EXPIRE_DAYS = 30

# 评级选项
RATING_OPTIONS = ["可信", "中等", "存疑", "虚假"]

# 评级映射（用于规范化模型输出）
RATING_MAPPING = {
    "可信": "可信",
    "可信赖": "可信",
    "可靠": "可信",
    "中等": "中等",
    "一般": "中等",
    "普通": "中等",
    "存疑": "存疑",
    "可疑": "存疑",
    "存疑": "存疑",
    "假新闻": "虚假",
    "虚假": "虚假",
    "谣言": "虚假",
    "不可信": "虚假",
}


def _normalize_rating(rating: str) -> str:
    """规范化评级结果"""
    if not rating:
        return "存疑"
    for key, value in RATING_MAPPING.items():
        if key in rating:
            return value
    # 默认返回"存疑"
    if rating in RATING_OPTIONS:
        return rating
    return "存疑"


def _extract_media_info(input_str: str) -> Tuple[str, Optional[str]]:
    """
    从输入中提取媒体名称和域名

    Returns:
        (media_name, domain)
    """
    input_str = input_str.strip()

    # 如果是URL，提取域名
    if input_str.startswith(("http://", "https://", "www.")):
        domain = input_str
        if domain.startswith("www."):
            domain = domain[4:]
        # 提取主域名
        match = re.match(r'(?:https?://)?(?:www\.)?([^/]+)', domain)
        if match:
            domain = match.group(1)
        # 从域名推断媒体名称
        name = _infer_media_name(domain)
        return name, domain

    # 直接是媒体名称
    return input_str, None


def _infer_media_name(domain: str) -> str:
    """从域名推断媒体名称"""
    domain_lower = domain.lower()

    # 常见媒体域名映射
    MEDIA_NAMES = {
        "sina.com.cn": "新浪",
        "sohu.com": "搜狐",
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
        "feng.com": "蜂鸟网",
    }

    for key, name in MEDIA_NAMES.items():
        if key in domain_lower:
            return name

    # 尝试从域名提取
    parts = domain_lower.split(".")
    if len(parts) >= 2:
        return parts[0].capitalize()

    return domain


def _build_rating_prompt(media_name: str, domain: Optional[str] = None) -> Tuple[str, str]:
    """
    构建评级提示词

    Returns:
        (system_prompt, user_prompt)
    """
    system_prompt = """你是一位专业的媒体可靠性评估专家。

你的任务是：
1. 对给定的媒体进行可靠性评估
2. 评级必须是四选一：可信 / 中等 / 存疑 / 虚假
3. 必须通过联网搜索收集证据

评估依据：
- 是否在国家网信办公告的许可名单内
- 是否被中国互联网联合辟谣平台收录
- 是否被官方约谈、处罚或点名
- 是否存在标题党、洗稿、虚假新闻等问题
- 域名是否疑似仿冒正规媒体

输出格式（严格JSON）：
{
    "rating": "可信/中等/存疑/虚假",
    "evidence": ["证据1（来源）", "证据2（来源）"],
    "reason": "一句话总结评估理由"
}

要求：
- 所有结论必须有搜索来源支撑
- 证据需标注来源网站
- 如果信息不足，给出"存疑"评级"""

    domain_info = f"域名：{domain}" if domain else ""
    user_prompt = f"""请评估以下媒体的可靠性：

媒体名称：{media_name}
{domain_info}

请联网搜索相关信息，给出评估结果。"""

    return system_prompt, user_prompt


def _parse_json_response(response: str) -> dict:
    """解析大模型返回的JSON响应"""
    default_result = {
        "rating": "存疑",
        "evidence": ["分析结果解析异常"],
        "reason": "无法获取有效分析结果，请手动核实"
    }

    if not response:
        return default_result

    try:
        # 尝试直接解析
        result = json.loads(response)
        if "rating" in result:
            result["rating"] = _normalize_rating(result["rating"])
            return result
    except json.JSONDecodeError:
        pass

    # 尝试提取JSON块
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'\{[\s\S]*"rating"[\s\S]*\}',
        r'\{[\s\S]*"reason"[\s\S]*"evidence"[\s\S]*\}',
    ]

    for pattern in patterns:
        match = re.search(pattern, response)
        if match:
            try:
                json_str = match.group(1) if '```' in pattern else match.group()
                result = json.loads(json_str)
                if "rating" in result:
                    result["rating"] = _normalize_rating(result["rating"])
                    return result
            except (json.JSONDecodeError, IndexError):
                continue

    logger.warning("无法解析大模型响应: {}", response[:200])
    return default_result


async def get_rating_from_bailian(
    media_name: str,
    domain: Optional[str] = None
) -> dict:
    """
    调用百炼大模型对媒体进行评级

    Args:
        media_name: 媒体名称
        domain: 媒体域名

    Returns:
        {"rating": str, "evidence": list, "reason": str}
    """
    logger.info("开始评估媒体: name={}, domain={}", media_name, domain)

    system_prompt, user_prompt = _build_rating_prompt(media_name, domain)

    try:
        # 调用百炼大模型
        response = await chat_with_ai([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], enable_search=True)

        logger.debug("百炼响应: {}", response[:500] if response else "空")

        # 解析响应
        result = _parse_json_response(response)

        # 确保结果完整
        result.setdefault("rating", "存疑")
        result.setdefault("evidence", [])
        result.setdefault("reason", "分析完成")

        logger.info("媒体评级完成: rating={}", result["rating"])
        return result

    except Exception as e:
        logger.exception("调用百炼评估失败: {}", e)
        return {
            "rating": "存疑",
            "evidence": [f"调用异常: {str(e)}"],
            "reason": "服务暂时不可用，请稍后重试"
        }


async def get_rating_cached(
    db: AsyncSession,
    domain: str
) -> Optional[dict]:
    """
    从数据库缓存获取评级结果

    Args:
        db: 数据库会话
        domain: 媒体域名

    Returns:
        缓存结果或None
    """
    if not domain:
        return None

    try:
        result = await db.execute(
            select(MediaReliability).where(MediaReliability.domain == domain)
        )
        record = result.scalar_one_or_none()

        if record and not record.is_expired(CACHE_EXPIRE_DAYS):
            logger.info("使用缓存评级: domain={}, rating={}", domain, record.rating)
            return {
                "rating": record.rating,
                "reason": record.reason,
                "evidence": record.evidence_list,
                "source": "缓存",
                "cached": True
            }
    except Exception as e:
        logger.warning("查询缓存失败: {}", e)

    return None


async def save_rating_to_cache(
    db: AsyncSession,
    media_name: str,
    domain: Optional[str],
    result: dict
) -> None:
    """
    保存评级结果到数据库缓存

    Args:
        db: 数据库会话
        media_name: 媒体名称
        domain: 媒体域名
        result: 评级结果
    """
    if not domain:
        return

    try:
        # 检查是否已存在
        existing = await db.execute(
            select(MediaReliability).where(MediaReliability.domain == domain)
        )
        record = existing.scalar_one_or_none()

        if record:
            # 更新现有记录
            record.name = media_name
            record.rating = result.get("rating", "存疑")
            record.reason = result.get("reason", "")
            record.evidence_list = result.get("evidence", [])
            record.last_verified = date.today()
            record.source = "百炼大模型"
        else:
            # 创建新记录
            new_record = MediaReliability(
                domain=domain,
                name=media_name,
                rating=result.get("rating", "存疑"),
                reason=result.get("reason", ""),
                source="百炼大模型",
                last_verified=date.today()
            )
            new_record.evidence_list = result.get("evidence", [])
            db.add(new_record)

        await db.commit()
        logger.info("评级结果已缓存: domain={}, rating={}", domain, result.get("rating"))

    except Exception as e:
        logger.warning("保存缓存失败: {}", e)
        await db.rollback()


async def get_rating_cached_or_bailian(
    media_name: str,
    domain: Optional[str],
    db: AsyncSession,
    force_refresh: bool = False
) -> dict:
    """
    获取媒体评级，优先使用缓存

    Args:
        media_name: 媒体名称
        domain: 媒体域名
        db: 数据库会话
        force_refresh: 是否强制刷新

    Returns:
        {"rating": str, "evidence": list, "reason": str, "source": str, ...}
    """
    # 1. 尝试从缓存获取
    if not force_refresh and domain:
        cached = await get_rating_cached(db, domain)
        if cached:
            return cached

    # 2. 调用百炼进行评估
    logger.info("缓存未命中或已过期，调用百炼评估: {}", media_name)
    bailian_result = await get_rating_from_bailian(media_name, domain)

    # 3. 保存到缓存
    if domain:
        await save_rating_to_cache(db, media_name, domain, bailian_result)

    # 4. 返回结果
    bailian_result["source"] = "百炼大模型"
    bailian_result["cached"] = False
    return bailian_result


async def batch_get_ratings(
    db: AsyncSession,
    items: List[dict]
) -> List[dict]:
    """
    批量获取媒体评级

    Args:
        db: 数据库会话
        items: [{"name": str, "domain": str}, ...]

    Returns:
        评级结果列表
    """
    results = []
    for item in items:
        name = item.get("name", "")
        domain = item.get("domain")
        result = await get_rating_cached_or_bailian(name, domain, db)
        result["name"] = name
        result["domain"] = domain
        results.append(result)

    return results
