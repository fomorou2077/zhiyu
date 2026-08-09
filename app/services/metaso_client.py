"""
秘塔搜索 API 客户端
封装秘塔 /api/v1/search 接口，Bearer Token 认证、超时重试、标准化返回。

接口参数（已确认）：
  - q              查询文本（必填）
  - scope          搜索范围，默认 "all"
  - size           返回条数，默认 10
  - includeSummary 是否包含摘要，默认 true
  - 不需要 searchTopicId
"""

import time
import httpx
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.logger import logger


async def search(
    q: str,
    scope: str = "all",
    size: int = 10,
    include_summary: bool = True,
) -> Dict[str, Any]:
    """
    调用秘塔 /api/v1/search 进行语义搜索。

    Args:
        q:               查询文本
        scope:           搜索范围，默认 "all"
        size:            返回条数，默认 10
        include_summary: 是否包含摘要，默认 True

    Returns:
        {
            "success": bool,
            "text": str,
            "references": [{"title": ..., "url": ..., "snippet": ...}],
            "raw": dict | None,
            "error": str | None,
        }
    """
    if not settings.metaso_api_key:
        return {
            "success": False,
            "text": "",
            "references": [],
            "raw": None,
            "error": "秘塔 API Key 未配置，请在 .env 中设置 METASO_API_KEY",
        }

    headers = {
        "Authorization": f"Bearer {settings.metaso_api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "q": q,
        "scope": scope,
        "size": size,
        "includeSummary": include_summary,
    }

    last_error: Optional[Exception] = None

    for attempt in range(1, settings.max_retries + 1):
        start_time = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.request_timeout),
            ) as client:
                logger.info(
                    "秘塔搜索请求(第{}次): q={}, scope={}, size={}",
                    attempt,
                    q[:100],
                    scope,
                    size,
                )
                response = await client.post(
                    settings.metaso_base_url,
                    headers=headers,
                    json=payload,
                )
                elapsed = time.time() - start_time
                logger.info(
                    "秘塔搜索响应: status={}, elapsed={:.2f}s",
                    response.status_code,
                    elapsed,
                )

                if response.status_code == 401:
                    return {
                        "success": False,
                        "text": "",
                        "references": [],
                        "raw": None,
                        "error": "秘塔 API Key 无效或已过期",
                    }
                if response.status_code == 402:
                    return {
                        "success": False,
                        "text": "",
                        "references": [],
                        "raw": None,
                        "error": "秘塔 API 额度不足",
                    }
                if response.status_code == 429:
                    logger.warning("秘塔 API 限流(429)，等待后重试")
                    await _async_sleep(2 * attempt)
                    continue

                response.raise_for_status()
                data = response.json()

                text, references = _parse_metaso_response(data)

                logger.info(
                    "秘塔搜索成功: text_len={}, refs_count={}",
                    len(text),
                    len(references),
                )
                return {
                    "success": True,
                    "text": text,
                    "references": references,
                    "raw": data,
                    "error": None,
                }

        except httpx.TimeoutException as e:
            last_error = e
            logger.warning(
                "秘塔搜索超时(第{}次, {}s): {}",
                attempt,
                settings.request_timeout,
                e,
            )
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.error(
                "秘塔搜索HTTP错误(第{}次): status={}, body={}",
                attempt,
                e.response.status_code,
                e.response.text[:300],
            )
            if 400 <= e.response.status_code < 500:
                break
        except Exception as e:
            last_error = e
            logger.exception("秘塔搜索异常(第{}次): {}", attempt, e)

        if attempt < settings.max_retries:
            await _async_sleep(1.0 * attempt)

    logger.error("秘塔搜索全部重试失败: {}", last_error)
    return {
        "success": False,
        "text": "",
        "references": [],
        "raw": None,
        "error": f"请求失败（已重试{settings.max_retries}次）: {last_error}",
    }


def _parse_metaso_response(data: Dict[str, Any]) -> tuple:
    """
    解析秘塔 API 原始响应，提取文本和引用。
    """
    text = ""
    references: List[Dict[str, Any]] = []

    for key in ("text", "answer", "content", "result", "summary"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            text = val
            break

    if not text:
        inner = data.get("data", {})
        if isinstance(inner, dict):
            for key in ("text", "answer", "content", "result", "summary"):
                val = inner.get(key)
                if isinstance(val, str) and val.strip():
                    text = val
                    break
        if not text:
            messages = data.get("messages") or data.get("data", {}).get("messages") or []
            if isinstance(messages, list):
                parts = []
                for msg in messages:
                    if isinstance(msg, dict):
                        parts.append(msg.get("content") or msg.get("text") or "")
                text = "\n".join(p for p in parts if p)

    refs = (
        data.get("references")
        or data.get("sources")
        or data.get("data", {}).get("references")
        or data.get("data", {}).get("sources")
        or []
    )
    if isinstance(refs, list):
        for ref in refs:
            if isinstance(ref, dict):
                references.append({
                    "title": ref.get("title", ""),
                    "url": ref.get("url", ""),
                    "snippet": ref.get("snippet") or ref.get("content") or "",
                })

    return text, references


async def _async_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)
