"""
报告生成 API 路由
"""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.report_generator import call_coze_workflow

router = APIRouter(prefix="/api/report", tags=["报告生成"])


class GenerateRequest(BaseModel):
    user_id: int
    user_type: str  # "个人"、"自媒体"、"企业"
    time_range: str = "近 30 天"  # 分析时间范围


@router.post("/generate")
async def generate_report(req: GenerateRequest):
    """
    触发 Coze 工作流生成报告，返回流式 SSE。
    """
    if req.user_type not in ["个人", "自媒体", "企业"]:
        raise HTTPException(status_code=400, detail="无效的用户类型，仅支持：个人、自媒体、企业")

    async def event_stream():
        async for chunk in call_coze_workflow(req.user_id, req.user_type, req.time_range):
            # 确保是有效内容才发送
            if chunk:
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: {\"content\": \"\", \"done\": true}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
