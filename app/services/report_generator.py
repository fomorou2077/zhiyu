"""
报告生成服务：调用 Coze 工作流生成流式报告
"""
import json
import httpx
from typing import AsyncGenerator
from app.config import settings


async def call_coze_workflow(user_id: int, user_type: str, time_range: str = "近 30 天") -> AsyncGenerator[str, None]:
    """
    调用 Coze 工作流，返回报告内容。
    user_type: "个人"、"自媒体"、"企业"
    time_range: 分析时间范围，默认 "近 30 天"
    """
    if not settings.coze_api_url or not settings.coze_api_token:
        yield "【配置错误】Coze API 未配置，请联系管理员。"
        return

    headers = {
        "Authorization": f"Bearer {settings.coze_api_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "user_id": str(user_id),
        "user_type": user_type,
        "time_range": time_range,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                settings.coze_api_url,
                headers=headers,
                json=payload,
            )

            if response.status_code == 402:
                yield "【额度不足】Coze API 余额不足或 Token 已过期，请续费后重试。"
                return
            if response.status_code == 401:
                yield "【认证失败】Coze API Token 无效或已过期，请检查配置。"
                return
            if response.status_code == 403:
                yield "【权限不足】Coze API 无权访问该工作流，请检查 API 权限设置。"
                return

            response.raise_for_status()

            text = response.text.strip()
            if not text:
                return

            # 先尝试 SSE 流式解析
            sse_parsed = False
            for line in text.split("\n"):
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    parsed = json.loads(data)
                    content = (
                        parsed.get("content")
                        or parsed.get("text")
                        or parsed.get("message", {}).get("content")
                        or str(parsed)
                    )
                    if content:
                        yield content
                    if parsed.get("is_end") or parsed.get("done"):
                        sse_parsed = True
                        break
                except json.JSONDecodeError:
                    if data:
                        yield data
            if sse_parsed:
                return

            # 非 SSE 流式，尝试直接解析为 JSON
            try:
                parsed = json.loads(text)
                # 优先返回 markdown 报告内容
                report = parsed.get("report_markdown") or parsed.get("content") or parsed.get("text")
                if report:
                    yield report
                elif parsed:
                    yield json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                # 原始文本直接返回
                yield text
    except httpx.TimeoutException:
        yield "\n\n【请求超时】Coze 工作流响应超时，请稍后重试。"
    except httpx.HTTPStatusError as e:
        yield f"\n\n【请求失败】HTTP {e.response.status_code}：{e.response.text[:200]}"
    except Exception as e:
        yield f"\n\n【系统错误】{type(e).__name__}: {str(e)}"
