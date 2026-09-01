"""
MIROFISH 模拟服务客户端

封装 MIROFISH 本地 Docker 服务的 HTTP 调用：
  POST /api/simulation/prepare       → 创建模拟任务
  POST /api/simulation/run/{id}      → 执行模拟
  GET  /api/report/{id}              → 获取报告

以及一键全流程方法 full_pipeline()。

依赖：仅使用 requests（同步），不依赖 pydantic/httpx。
"""

import time
import requests

from app.config import settings
from typing import Any, Dict, Optional, Tuple

# ============================================================
# 配置（从 app.config.settings 读取，支持 .env 中的 MIROFISH_BASE_URL）
# ============================================================

MIROFISH_BASE = settings.mirofish_base_url
TIMEOUT = 60          # 模拟可能耗时较长
MAX_RETRIES = 2


# ============================================================
# 内部工具
# ============================================================

def _post(path: str, json_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any, Optional[str]]:
    """
    同步 POST 请求，返回 (success, data, error_message)。

    Args:
        path:      接口路径，如 "/api/simulation/prepare"
        json_data: JSON 请求体

    Returns:
        (success: bool, data: dict|None, error: str|None)
    """
    url = f"{MIROFISH_BASE}{path}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                json=json_data or {},
                timeout=TIMEOUT,
            )

            if resp.status_code == 200:
                try:
                    return True, resp.json(), None
                except Exception:
                    return True, {"raw": resp.text}, None

            # 客户端或服务端错误
            error_msg = f"MIROFISH 返回 HTTP {resp.status_code}"
            try:
                body = resp.json()
                if isinstance(body, dict):
                    detail = body.get("detail") or body.get("message") or body.get("error")
                    if detail:
                        error_msg += f": {detail}"
            except Exception:
                error_msg += f": {resp.text[:200]}"

            if 400 <= resp.status_code < 500:
                return False, None, error_msg   # 4xx 不重试

        except requests.ConnectionError:
            if attempt == MAX_RETRIES:
                return False, None, (
                    f"无法连接 MIROFISH 服务 ({MIROFISH_BASE})。"
                    f"请确认 Docker 已启动且 MIROFISH 容器正在运行。"
                    f"可执行 docker ps 检查容器状态。"
                )
            time.sleep(1 * attempt)

        except requests.Timeout:
            if attempt == MAX_RETRIES:
                return False, None, f"MIROFISH 请求超时（>{TIMEOUT}s），请稍后重试。"
            time.sleep(1 * attempt)

        except Exception as e:
            if attempt == MAX_RETRIES:
                return False, None, f"MIROFISH 请求异常: {type(e).__name__}: {e}"
            time.sleep(1 * attempt)

    return False, None, "MIROFISH 请求失败（未知原因）"


def _get(path: str) -> Tuple[bool, Any, Optional[str]]:
    """同步 GET 请求"""
    url = f"{MIROFISH_BASE}{path}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT)

            if resp.status_code == 200:
                try:
                    return True, resp.json(), None
                except Exception:
                    return True, {"raw": resp.text}, None

            error_msg = f"MIROFISH 返回 HTTP {resp.status_code}"
            try:
                body = resp.json()
                if isinstance(body, dict):
                    detail = body.get("detail") or body.get("message") or body.get("error")
                    if detail:
                        error_msg += f": {detail}"
            except Exception:
                error_msg += f": {resp.text[:200]}"

            if 400 <= resp.status_code < 500:
                return False, None, error_msg

        except requests.ConnectionError:
            if attempt == MAX_RETRIES:
                return False, None, (
                    f"无法连接 MIROFISH 服务 ({MIROFISH_BASE})。"
                    f"请确认 Docker 已启动且 MIROFISH 容器正在运行。"
                )
            time.sleep(1 * attempt)

        except requests.Timeout:
            if attempt == MAX_RETRIES:
                return False, None, f"MIROFISH 请求超时（>{TIMEOUT}s），请稍后重试。"
            time.sleep(1 * attempt)

        except Exception as e:
            if attempt == MAX_RETRIES:
                return False, None, f"MIROFISH 请求异常: {type(e).__name__}: {e}"
            time.sleep(1 * attempt)

    return False, None, "MIROFISH 请求失败（未知原因）"


# ============================================================
# 公开接口
# ============================================================

def prepare_simulation(content: str, requirement: str = "") -> Dict[str, Any]:
    """
    准备模拟：上传文本内容，创建模拟任务。

    Args:
        content:     需要模拟分析的黑稿/负面舆情文本内容
        requirement: 模拟需求描述（可选，如"预测7天内发酵趋势"）

    Returns:
        {"success": bool, "data": dict|None, "error": str|None}
        成功时 data 包含 simulation_id
    """
    payload: Dict[str, Any] = {"content": content}
    if requirement:
        payload["requirement"] = requirement

    success, data, error = _post("/api/simulation/prepare", payload)

    if success and isinstance(data, dict):
        sim_id = data.get("simulation_id") or data.get("id") or data.get("simulationId")
        return {
            "success": True,
            "data": {
                "simulation_id": sim_id,
                "raw": data,
            },
            "error": None,
        }

    return {"success": False, "data": None, "error": error or "准备模拟失败"}


def run_simulation(simulation_id: str) -> Dict[str, Any]:
    """
    运行模拟：触发指定模拟任务的执行。

    Args:
        simulation_id: 模拟任务 ID

    Returns:
        {"success": bool, "data": dict|None, "error": str|None}
    """
    success, data, error = _post(f"/api/simulation/run/{simulation_id}")

    if success:
        return {"success": True, "data": data, "error": None}

    return {"success": False, "data": None, "error": error or "运行模拟失败"}


def get_report(simulation_id: str) -> Dict[str, Any]:
    """
    获取模拟报告。

    Args:
        simulation_id: 模拟任务 ID

    Returns:
        {"success": bool, "data": dict|None, "error": str|None}
        成功时 data 包含完整报告内容
    """
    success, data, error = _get(f"/api/report/{simulation_id}")

    if success:
        return {"success": True, "data": data, "error": None}

    return {"success": False, "data": None, "error": error or "获取报告失败"}


def full_pipeline(content: str, requirement: str = "") -> Dict[str, Any]:
    """
    一键全流程：准备 → 运行 → 获取报告。

    用户输入一段黑稿文本，直接返回舆情模拟预测报告。

    Args:
        content:     需要模拟分析的黑稿/负面舆情文本内容
        requirement: 模拟需求描述（可选）

    Returns:
        {
            "success": bool,
            "message": str,
            "data": {
                "simulation_id": str,
                "report": dict | None,
            },
            "error": str | None,
        }
    """
    # 步骤 1：准备模拟
    prepare_result = prepare_simulation(content, requirement)
    if not prepare_result["success"]:
        return {
            "success": False,
            "message": "模拟准备失败",
            "data": None,
            "error": prepare_result["error"],
        }

    sim_id = prepare_result["data"]["simulation_id"] if prepare_result["data"] else None
    if not sim_id:
        return {
            "success": False,
            "message": "模拟准备成功但未返回 simulation_id",
            "data": prepare_result["data"],
            "error": "MIROFISH 返回数据中缺少 simulation_id",
        }

    # 步骤 2：运行模拟
    run_result = run_simulation(sim_id)
    if not run_result["success"]:
        return {
            "success": False,
            "message": f"模拟已创建(sim_id={sim_id})但运行失败",
            "data": {"simulation_id": sim_id},
            "error": run_result["error"],
        }

    # 步骤 3：获取报告（模拟可能需要一定时间，轮询等待）
    max_polls = 10
    for poll in range(1, max_polls + 1):
        report_result = get_report(sim_id)
        if report_result["success"]:
            return {
                "success": True,
                "message": "模拟推演完成",
                "data": {
                    "simulation_id": sim_id,
                    "report": report_result["data"],
                },
                "error": None,
            }
        # 如果报告还没生成好，等待后重试
        if poll < max_polls:
            time.sleep(2)

    return {
        "success": False,
        "message": "模拟已完成但获取报告超时",
        "data": {"simulation_id": sim_id},
        "error": f"已轮询{max_polls}次仍未获取到报告，请稍后通过 simulation_id 手动获取",
    }
