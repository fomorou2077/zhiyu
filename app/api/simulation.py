"""
模拟推演 API 路由

对接 MIROFISH 本地模拟服务，提供舆情模拟推演功能。

接口：
  POST /api/simulation/full          → 一键完成 准备→运行→获取报告
  GET  /api/simulation/report/{id}   → 获取历史报告

注意：不使用 pydantic BaseModel，直接用 fastapi.Body() 接收参数，
     避免 pydantic-core 在 Python 3.14 上的编译问题。
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

from app.services.mirofish_client import full_pipeline, get_report
from app.utils.logger import logger

router = APIRouter(prefix="/api/simulation", tags=["模拟推演"])


# ============================================================
# 辅助：统一响应格式
# ============================================================

def _ok(message: str = "", data: Any = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data, "error": None}


def _fail(message: str = "", error: Optional[str] = None) -> Dict[str, Any]:
    return {"success": False, "message": message, "data": None, "error": error}


# ============================================================
# 路由
# ============================================================

@router.post("/full")
def simulate_full(
    content: str = Body(..., description="需要模拟分析的黑稿/负面舆情文本内容"),
    requirement: str = Body("", description="模拟需求描述（可选）"),
):
    """
    一键模拟推演：输入舆情文本，自动完成「准备→运行→获取报告」全流程。

    请求体（JSON）：
      - content:     必填，黑稿文本内容
      - requirement: 可选，如"预测7天内发酵趋势"或"如果我发声明回应会怎样"

    返回：
      - success: 是否成功
      - message: 提示信息
      - data:    { simulation_id, report }
      - error:   错误信息（成功时为 null）
    """
    logger.info(
        "模拟推演请求: content_len={}, requirement={}",
        len(content),
        requirement[:100] if requirement else "(无)",
    )

    if not content.strip():
        return _fail("content 不能为空", "请提供需要模拟分析的文本内容")

    result = full_pipeline(content=content, requirement=requirement)

    if result["success"]:
        logger.info("模拟推演成功: simulation_id={}", result["data"]["simulation_id"])
        return _ok(
            message="模拟推演完成",
            data=result["data"],
        )
    else:
        logger.warning("模拟推演失败: {}", result["error"])
        return _fail(
            message=result["message"],
            error=result["error"],
        )


@router.get("/report/{simulation_id}")
def get_simulation_report(simulation_id: str):
    """
    获取历史模拟报告。

    路径参数：
      - simulation_id: 模拟任务 ID

    返回：
      - success: 是否成功
      - message: 提示信息
      - data:    报告内容
      - error:   错误信息（成功时为 null）
    """
    logger.info("获取模拟报告: simulation_id={}", simulation_id)

    if not simulation_id.strip():
        return _fail("simulation_id 不能为空")

    result = get_report(simulation_id=simulation_id)

    if result["success"]:
        logger.info("报告获取成功: simulation_id={}", simulation_id)
        return _ok(
            message="报告获取成功",
            data=result["data"],
        )
    else:
        logger.warning("报告获取失败: simulation_id={}, error={}", simulation_id, result["error"])
        return _fail(
            message="报告获取失败",
            error=result["error"],
        )
