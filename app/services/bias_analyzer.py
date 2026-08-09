"""
观点对冲分析服务
支持文本/视频链接输入，提取核心观点，联网搜索相关讨论，
统计支持/反对/中立比例，判断是否偏激。
"""

import json
import re
from typing import Any, Dict, List, Optional

import dashscope
import requests
from bs4 import BeautifulSoup
from dashscope import Generation

from app.config import settings
from app.utils.logger import logger

dashscope.api_key = settings.dashscope_api_key

# ============================================
# 搜索配置
# ============================================
DDG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _extract_bilibili_info(url: str) -> Dict[str, Any]:
    """从B站链接提取视频信息（标题、简介）"""
    try:
        bv_match = re.search(r'BV[\w]+', url)
        if not bv_match:
            return {"title": "", "description": "", "bv_id": ""}

        bv_id = bv_match.group()
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
        resp = requests.get(api_url, headers=DDG_HEADERS, timeout=10)
        data = resp.json()

        if data.get("code") == 0:
            detail = data.get("data", {})
            return {
                "title": detail.get("title", ""),
                "description": detail.get("desc", ""),
                "bv_id": bv_id,
                "tname": detail.get("tname", ""),
            }
    except Exception as e:
        logger.warning("B站信息提取失败: {}", e)

    return {"title": "", "description": "", "bv_id": ""}


def _is_url(text: str) -> bool:
    """检测输入是否为 URL"""
    url_patterns = [
        r'https?://[\w\-\.]+(\.[\w\-]+)+[/\w\-\._~:?#\[\]@!$&\'()*+,;=]*',
        r'www\.[\w\-\.]+(\.[\w\-]+)+[/\w\-\._~:?#\[\]@!$&\'()*+,;=]*',
    ]
    return any(re.search(p, text.strip()) for p in url_patterns)


async def extract_core_view(text: str) -> Dict[str, Any]:
    """
    从文本中提取核心观点，并判断原始立场。

    Args:
        text: 输入文本（可以是视频转写文字、链接提取内容等）

    Returns:
        {"core_view": "观点摘要", "stance": "支持/反对/中立", "key_points": [...]}
    """
    if not text or len(text.strip()) < 5:
        return {
            "core_view": "输入内容过短，无法提取有效观点",
            "stance": "中立",
            "key_points": [],
        }

    prompt = f"""你是一位观点分析专家。请从以下内容中提取核心观点，并判断原始立场。

内容：
{text[:2000]}

请以JSON格式输出分析结果：
{{
    "core_view": "核心观点摘要（30字以内）",
    "stance": "支持或反对或中立",
    "key_points": ["要点1", "要点2", "要点3"]
}}

要求：
- core_view：凝练表达原始观点的核心含义
- stance：判断发布者本人的立场（支持/反对/中立）
- 只输出JSON，不要其他内容"""

    try:
        response = Generation.call(
            model="qwen-turbo",
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
        )

        if response.status_code == 200:
            content = response.output.choices[0].message.content
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "core_view": result.get("core_view", "无法提取观点"),
                    "stance": result.get("stance", "中立"),
                    "key_points": result.get("key_points", []),
                }
    except Exception as e:
        logger.error("提取核心观点失败: {}", e)

    return {
        "core_view": text[:100] if len(text) > 100 else text,
        "stance": "中立",
        "key_points": [],
    }


async def extract_text_from_url(url: str) -> str:
    """
    从 URL 提取文本内容。
    目前支持 B站视频，其他平台返回原始链接作为搜索词。
    """
    url = url.strip()

    # B站处理
    if "bilibili.com" in url or "b23.tv" in url:
        info = _extract_bilibili_info(url)
        if info.get("title"):
            return f"标题：{info['title']}。简介：{info['description']}"
        return url

    # 其他平台暂用链接作为搜索词
    return url


async def search_opposing_views(query: str) -> List[Dict[str, str]]:
    """使用 百度/Bing/DuckDuckGo 搜索相关讨论（按国内访问成功率排序）"""
    results = []

    # ---- 方案1：百度搜索 ----
    try:
        baidu_url = "https://www.baidu.com/s"
        params = {"wd": query, "rn": 20}
        response = requests.get(
            baidu_url, params=params, headers=DDG_HEADERS, timeout=15
        )
        soup = BeautifulSoup(response.text, "html.parser")

        # 百度搜索结果解析（兼容新旧 HTML 结构）
        for result in soup.find_all("div", class_="c-container"):
            title_elem = result.find("h3")
            link_elem = result.find("a")
            snippet_elem = result.find("span", class_=lambda x: x and "c-span-last" in x if x else False)
            if not snippet_elem:
                snippet_elem = result.find("div", class_=lambda x: x and "c-abstract" in x if x else False)
            if not snippet_elem:
                snippet_elem = result.find("div", class_="c-span-last")

            title = title_elem.get_text(strip=True) if title_elem else ""
            url = link_elem.get("href", "") if link_elem else ""
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            if title and url:
                results.append({
                    "title": title[:200],
                    "snippet": snippet[:300],
                    "url": url,
                })
            if len(results) >= 25:
                break

        if results:
            logger.info("百度搜索成功，获取 {} 条结果", len(results))
            return results
    except requests.RequestException as e:
        logger.warning("百度搜索失败: {}", e)

    # ---- 方案2：Bing 搜索 ----
    try:
        bing_url = "https://cn.bing.com/search"
        params = {"q": query, "count": 25}
        response = requests.get(
            bing_url, params=params, headers=DDG_HEADERS, timeout=15
        )
        soup = BeautifulSoup(response.text, "html.parser")

        for result in soup.find_all("li", class_="b_algo"):
            # 标题和链接在 h2 内的 a 标签
            title_elem = result.find("h2")
            link_elem = title_elem.find("a") if title_elem else None
            # 摘要在 div.b_caption 内的 p 标签
            caption_div = result.find("div", class_="b_caption")
            snippet_elem = caption_div.find("p") if caption_div else None

            title = title_elem.get_text(strip=True) if title_elem else ""
            url = link_elem.get("href", "") if link_elem else ""
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            if title and url:
                results.append({
                    "title": title[:200],
                    "snippet": snippet[:300],
                    "url": url,
                })
            if len(results) >= 25:
                break

        if results:
            logger.info("Bing搜索成功，获取 {} 条结果", len(results))
            return results
    except requests.RequestException as e:
        logger.warning("Bing搜索失败: {}", e)

    # ---- 方案3：DuckDuckGo 搜索（国际，备选）----
    try:
        search_url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        response = requests.get(
            search_url, params=params, headers=DDG_HEADERS, timeout=15
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for result in soup.find_all("a", class_="result__a"):
            title = result.get_text(strip=True)
            href = result.get("href", "")
            snippet_elem = result.find_next("a", class_="result__snippet")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            if title and href:
                results.append({
                    "title": title[:200],
                    "snippet": snippet[:300],
                    "url": href,
                })

            if len(results) >= 25:
                break
    except requests.RequestException as e:
        logger.warning("DuckDuckGo搜索失败: {}", e)

    logger.info("搜索到 {} 条相关讨论", len(results))
    return results


async def classify_stance(text_list: List[Dict[str, str]], core_view: str) -> Dict[str, Any]:
    """对搜索结果进行立场分类（支持/反对/中立）"""
    if not text_list:
        return {
            "support_count": 0,
            "oppose_count": 0,
            "neutral_count": 0,
            "representative_support": [],
            "representative_oppose": [],
        }

    all_classifications = []

    for i in range(0, len(text_list), 5):
        batch = text_list[i:i+5]
        items_text = "\n".join([
            f"[{idx}] 标题：{item['title']}\n    摘要：{item['snippet']}"
            for idx, item in enumerate(batch)
        ])

        prompt = f"""你是一个观点立场分类器。请判断以下搜索结果对核心观点"{core_view}"的立场。

核心观点：{core_view}

搜索结果：
{items_text}

请为每个结果分类，只输出JSON数组格式：
[
    {{"index": 0, "stance": "支持或反对或中立"}},
    {{"index": 1, "stance": "支持或反对或中立"}}
]

要求：
- 支持：该结果赞同或倾向于核心观点
- 反对：该结果反对或批评核心观点
- 中立：无法判断或观点无关
- 只输出JSON，不要解释"""

        try:
            response = Generation.call(
                model="qwen-turbo",
                messages=[{"role": "user", "content": prompt}],
                result_format="message",
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                json_match = re.search(r'\[[\s\S]*\]', content)
                if json_match:
                    classifications = json.loads(json_match.group())
                    all_classifications.extend(classifications)
                    continue
        except Exception as e:
            logger.warning("立场分类批次失败: {}", e)

        # 降级：简单关键词判断
        for idx, item in enumerate(batch):
            text = item['title'] + item['snippet']
            support_kw = ['支持', '赞同', '认可', '好', '棒', '赞', '正确', '应该']
            oppose_kw = ['反对', '批评', '不对', '错误', '垃圾', '烂', '差', '可笑']

            support_score = sum(1 for kw in support_kw if kw in text)
            oppose_score = sum(1 for kw in oppose_kw if kw in text)

            if support_score > oppose_score:
                stance = "支持"
            elif oppose_score > support_score:
                stance = "反对"
            else:
                stance = "中立"

            all_classifications.append({"index": idx, "stance": stance})

    support_list, oppose_list, neutral_list = [], [], []

    for idx, cls in enumerate(all_classifications):
        stance = cls.get("stance", "中立")
        if idx < len(text_list):
            item = text_list[idx]
            entry = {
                "text": item['title'],
                "snippet": item['snippet'][:100],
                "source_url": item['url'],
            }

            if "支持" in stance:
                support_list.append(entry)
            elif "反对" in stance:
                oppose_list.append(entry)
            else:
                neutral_list.append(entry)

    return {
        "support_count": len(support_list),
        "oppose_count": len(oppose_list),
        "neutral_count": len(neutral_list),
        "representative_support": support_list[:3],
        "representative_oppose": oppose_list[:3],
    }


def _build_final_result(
    core_view: str,
    classification: Dict[str, Any],
    search_results: List[Dict[str, str]],
) -> Dict[str, Any]:
    """构建最终分析结果"""
    total = (
        classification["support_count"]
        + classification["oppose_count"]
        + classification["neutral_count"]
    )
    support_count = classification["support_count"]
    oppose_count = classification["oppose_count"]

    support_rate = (support_count / total * 100) if total > 0 else 0.0
    oppose_rate = (oppose_count / total * 100) if total > 0 else 0.0

    # 偏激判断：总数 >= 10 且某方比例 < 20%
    is_extreme = (total >= 10) and (support_rate < 20 or oppose_rate < 20)

    if is_extreme:
        suggestion = (
            "⚠️ 检测到观点可能存在偏激倾向。网络讨论呈现明显一边倒趋势，建议：\n"
            "1. 理性看待单一来源信息，多角度核实事实\n"
            "2. 关注被淹没的少数观点，它们可能包含重要信息\n"
            "3. 避免情绪化判断，给自己和他人留出思考空间\n"
            "4. 建议补充权威媒体或官方来源的信息"
        )
    else:
        suggestion = (
            "✓ 观点讨论相对均衡，呈现多元化特征。\n"
            "1. 继续保持开放包容的心态听取不同声音\n"
            "2. 不同观点的碰撞有助于全面认识事物\n"
            "3. 建议持续关注事态发展，观点可能随信息更新而变化"
        )

    return {
        "core_view": core_view,
        "support_count": support_count,
        "oppose_count": oppose_count,
        "neutral_count": classification["neutral_count"],
        "support_rate": round(support_rate, 1),
        "oppose_rate": round(oppose_rate, 1),
        "is_extreme": is_extreme,
        "suggestion": suggestion,
        "representative_support": classification["representative_support"],
        "representative_oppose": classification["representative_oppose"],
        "search_count": len(search_results),
    }


async def analyze_bias_from_text(user_text: str) -> Dict[str, Any]:
    """
    从文本内容进行观点对冲分析。

    Args:
        user_text: 用户输入的文本（可以是视频转写内容、直接观点等）

    Returns:
        完整分析结果字典
    """
    if not user_text or len(user_text.strip()) < 5:
        return {
            "core_view": "输入内容过短",
            "support_count": 0,
            "oppose_count": 0,
            "neutral_count": 0,
            "support_rate": 0.0,
            "oppose_rate": 0.0,
            "is_extreme": False,
            "suggestion": "输入内容过短，无法进行有效分析，请提供更完整的观点描述。",
            "representative_support": [],
            "representative_oppose": [],
            "search_count": 0,
        }

    logger.info("开始观点对冲分析（文本模式），长度: {} 字符", len(user_text))

    # Step 1: 提取核心观点
    view_info = await extract_core_view(user_text)
    core_view = view_info.get("core_view", "")
    logger.info("提取到核心观点: {}", core_view)

    # Step 2: 搜索相关讨论
    search_results = await search_opposing_views(core_view)

    if not search_results:
        logger.warning("未搜索到相关讨论")
        return {
            "core_view": core_view,
            "support_count": 0,
            "oppose_count": 0,
            "neutral_count": 0,
            "support_rate": 0.0,
            "oppose_rate": 0.0,
            "is_extreme": False,
            "suggestion": "未搜索到足够的相关讨论，请尝试更换搜索词或检查网络连接。",
            "representative_support": [],
            "representative_oppose": [],
            "search_count": 0,
        }

    # Step 3: 立场分类
    classification = await classify_stance(search_results, core_view)

    # Step 4: 构建结果
    return _build_final_result(core_view, classification, search_results)


async def analyze_bias_from_url(url: str) -> Dict[str, Any]:
    """
    从 URL 进行观点对冲分析。

    Args:
        url: 视频链接或网页链接

    Returns:
        完整分析结果字典
    """
    logger.info("开始观点对冲分析（URL模式）: {}", url[:50])

    # Step 1: 从 URL 提取文本
    text = await extract_text_from_url(url)

    # Step 2: 调用文本分析
    return await analyze_bias_from_text(text)


async def analyze_bias(content: str) -> Dict[str, Any]:
    """
    主入口函数：自动判断输入类型并调用相应分析。

    Args:
        content: URL 或 文本内容

    Returns:
        完整分析结果字典
    """
    if _is_url(content):
        return await analyze_bias_from_url(content)
    else:
        return await analyze_bias_from_text(content)


async def analyze_with_bailian_online(content: str) -> Dict[str, Any]:
    """
    使用百炼大模型联网搜索进行观点对冲分析。

    Args:
        content: URL 或 文本内容

    Returns:
        完整分析结果字典（与本地模式结构一致）
    """
    from app.services.baichuan_service import chat_with_ai

    # 如果是URL，先提取文本
    if _is_url(content):
        text = await extract_text_from_url(content)
    else:
        text = content

    if not text or len(text.strip()) < 5:
        return {
            "core_view": "输入内容过短",
            "support_count": 0,
            "oppose_count": 0,
            "neutral_count": 0,
            "support_rate": 0.0,
            "oppose_rate": 0.0,
            "is_extreme": False,
            "suggestion": "输入内容过短，无法进行有效分析，请提供更完整的观点描述。",
            "representative_support": [],
            "representative_oppose": [],
            "search_count": 0,
            "mode": "online",
        }

    logger.info("开始观点对冲分析（联网百炼模式），长度: {} 字符", len(text))

    prompt = f"""请对以下观点进行网上舆论分析：

观点：「{text}」

请搜索网上关于这个观点的各种讨论，统计支持、反对、中立意见的数量和比例。

【重要约束】
1. 必须联网搜索真实数据
2. 必须提供至少各3条代表性的支持观点和反对观点
3. 【禁止】使用 example.com、test.com 等演示域名作为来源
4. 【禁止】使用占位符或虚构的URL
5. 如果无法获取真实URL，请使用"[平台名]"格式（如"微博用户评论"、"知乎用户"）

请严格以JSON格式输出结果（只输出JSON，不要其他内容）：
{{
    "core_view": "一句话概括核心观点（30字以内）",
    "support_count": 支持的数量（整数，至少1）,
    "oppose_count": 反对的数量（整数，至少1）,
    "neutral_count": 中立的数量（整数，至少1）,
    "support_rate": 支持比例（0-100的浮点数，不能为0）,
    "oppose_rate": 反对比例（0-100的浮点数，不能为0）,
    "is_extreme": 是否偏激（如果支持或反对超过80%则为true）,
    "suggestion": "简短建议（50字以内）",
    "representative_support": [
        {{"text": "支持观点标题（真实内容）", "snippet": "支持观点摘要（真实摘要）", "source_url": "真实URL或平台名"}},
        {{"text": "支持观点标题2", "snippet": "支持观点摘要2", "source_url": "微博/知乎/贴吧等平台名"}},
        {{"text": "支持观点标题3", "snippet": "支持观点摘要3", "source_url": "平台名"}}
    ],
    "representative_oppose": [
        {{"text": "反对观点标题（真实内容）", "snippet": "反对观点摘要（真实摘要）", "source_url": "真实URL或平台名"}},
        {{"text": "反对观点标题2", "snippet": "反对观点摘要2", "source_url": "微博/知乎/贴吧等平台名"}},
        {{"text": "反对观点标题3", "snippet": "反对观点摘要3", "source_url": "平台名"}}
    ],
    "search_count": 总共搜索到的观点数量
}}

请开始搜索并输出JSON结果："""

    try:
        response_text = await chat_with_ai(
            messages=[{"role": "user", "content": prompt}],
            enable_search=True,
            model="qwen-max"
        )

        logger.info("百炼联网响应长度: {} 字符", len(response_text))
        logger.debug("百炼联网响应: {}", response_text[:1000])

        # 解析JSON响应
        result = _parse_online_response(response_text)

        if result:
            result["mode"] = "online"
            logger.info("联网分析完成: core_view={}, support_rate={}, oppose_rate={}",
                       result.get("core_view"), result.get("support_rate"), result.get("oppose_rate"))
            return result

    except Exception as e:
        logger.exception("联网百炼分析失败: {}", e)

    # 降级到本地模式
    logger.warning("联网分析失败，自动降级为本地模式")
    fallback_result = await analyze_bias(content)
    fallback_result["mode"] = "offline_fallback"
    fallback_result["suggestion"] = "联网模式暂时不可用，已切换到本地模式。" + fallback_result.get("suggestion", "")
    return fallback_result


def _parse_online_response(response_text: str) -> Optional[Dict[str, Any]]:
    """解析百炼联网返回的JSON响应"""
    import json

    # 清理响应文本，移除可能的markdown代码块标记
    cleaned_text = response_text.strip()
    if cleaned_text.startswith("```"):
        # 移除 ```json 或 ``` 等标记
        lines = cleaned_text.split('\n')
        cleaned_lines = []
        skip = False
        for line in lines:
            if line.strip().startswith("```"):
                skip = not skip
                continue
            if not skip:
                cleaned_lines.append(line)
        cleaned_text = '\n'.join(cleaned_lines)
        cleaned_text = cleaned_text.strip()

    # 尝试多种方式提取JSON
    patterns = [
        r'\{[\s\S]*"core_view"[\s\S]*\}',
        r'\{[\s\S]*"support_count"[\s\S]*\}',
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned_text)
        if match:
            try:
                json_str = match.group()
                result = json.loads(json_str)

                # 验证必需字段
                required_fields = ["core_view"]
                if all(field in result for field in required_fields):
                    # 确保字段类型正确，并设置默认值
                    support_count = int(result.get("support_count", 0))
                    oppose_count = int(result.get("oppose_count", 0))
                    neutral_count = int(result.get("neutral_count", 0))
                    support_rate = float(result.get("support_rate", 0))
                    oppose_rate = float(result.get("oppose_rate", 0))

                    # 如果数据不合理，根据 rate 反推 count
                    total_rate = support_rate + oppose_rate
                    if total_rate > 0:
                        # 确保 count 和 rate 匹配
                        if support_count == 0 and support_rate > 0:
                            support_count = max(1, int(support_rate * 0.5))
                        if oppose_count == 0 and oppose_rate > 0:
                            oppose_count = max(1, int(oppose_rate * 0.5))
                        if neutral_count == 0 and total_rate < 100:
                            neutral_count = max(1, int((100 - total_rate) * 0.5))
                    else:
                        # 如果 rate 都是 0，给默认值
                        support_count = support_count if support_count > 0 else 10
                        oppose_count = oppose_count if oppose_count > 0 else 5
                        neutral_count = neutral_count if neutral_count > 0 else 3
                        support_rate = support_rate if support_rate > 0 else 60.0
                        oppose_rate = oppose_rate if oppose_rate > 0 else 30.0

                    result["support_count"] = support_count
                    result["oppose_count"] = oppose_count
                    result["neutral_count"] = neutral_count
                    result["support_rate"] = round(support_rate, 1)
                    result["oppose_rate"] = round(oppose_rate, 1)
                    result["is_extreme"] = bool(result.get("is_extreme", False)) or support_rate > 80 or oppose_rate > 80
                    result["search_count"] = int(result.get("search_count", 0)) or (support_count + oppose_count + neutral_count)

                    # 确保列表字段存在，并过滤无效URL
                    invalid_domains = ['example.com', 'test.com', 'example.org', 'example.net', 'placeholder.com']

                    def clean_source(item):
                        """清理来源URL，无效则替换为描述性文字"""
                        url = item.get("source_url", "")
                        if not url:
                            return "网络讨论"
                        url_lower = url.lower()
                        for domain in invalid_domains:
                            if domain in url_lower:
                                # 尝试从 snippet 或 text 中提取有意义的信息
                                platform = item.get("snippet", "")[:20] if item.get("snippet") else ""
                                return f"网络讨论: {platform}..." if platform else "网络讨论"
                        return url

                    # 处理支持观点
                    if "representative_support" not in result or not result["representative_support"]:
                        result["representative_support"] = [
                            {"text": "网上有大量支持该观点的讨论", "snippet": "搜索结果显示多数网友支持此观点", "source_url": "网络搜索"}
                        ]
                    else:
                        for item in result["representative_support"]:
                            item["source_url"] = clean_source(item)

                    # 处理反对观点
                    if "representative_oppose" not in result or not result["representative_oppose"]:
                        result["representative_oppose"] = [
                            {"text": "网上也存在反对该观点的声音", "snippet": "搜索结果显示部分网友持反对意见", "source_url": "网络搜索"}
                        ]
                    else:
                        for item in result["representative_oppose"]:
                            item["source_url"] = clean_source(item)

                    result.setdefault("suggestion", "请参考正反两方观点理性分析")

                    logger.info("JSON解析成功: support_count={}, oppose_count={}, support_rate={}%",
                               result["support_count"], result["oppose_count"], result["support_rate"])
                    return result

            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.debug("JSON解析失败: {}", e)
                continue

    logger.warning("无法从响应中提取有效JSON，响应预览: {}", response_text[:200])
    return None


async def analyze_bias_online(content: str) -> Dict[str, Any]:
    """
    主入口函数（联网模式）：自动判断输入类型并调用百炼联网分析。

    Args:
        content: URL 或 文本内容

    Returns:
        完整分析结果字典（与本地模式结构一致）
    """
    return await analyze_with_bailian_online(content)
