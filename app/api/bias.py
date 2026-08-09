"""
观点对冲分析 API 路由
"""

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.bias_analyzer import (
    analyze_bias,
    analyze_bias_from_text,
    analyze_with_bailian_online,
)
from app.services.video_to_text import (
    VideoToTextResult,
    cleanup_temp_file,
    extract_text_from_video_file,
    save_upload_file,
)
from app.utils.logger import logger

router = APIRouter(prefix="/bias", tags=["观点对冲"])


class BiasAnalyzeRequest(BaseModel):
    """观点对冲分析请求模型"""
    content: str
    use_online: bool = False


@router.post("/analyze")
async def analyze_text_endpoint(request: BiasAnalyzeRequest):
    """
    观点对冲分析接口 - 文本/链接模式

    Args:
        request: 包含 content 和 use_online 的请求体
    """
    content = request.content
    use_online = request.use_online

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="输入内容不能为空")

    try:
        if use_online:
            # 联网百炼模式
            logger.info("使用联网百炼模式分析: {}", content[:50])
            result = await analyze_with_bailian_online(content)
        else:
            # 本地搜索模式
            logger.info("使用本地搜索模式分析: {}", content[:50])
            result = await analyze_bias(content)

        result["analysis_mode"] = "online" if use_online else "offline"
        return result
    except Exception as e:
        logger.exception("观点分析失败: {}", e)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/analyze-video")
async def analyze_video_endpoint(
    file: UploadFile = File(..., description="视频文件"),
    user_text: Optional[str] = Form(None, description="可选的额外文本描述"),
    use_online: bool = Form(False, description="是否使用联网百炼模式"),
):
    """
    观点对冲分析接口 - 视频上传模式

    1. 保存上传的视频文件
    2. 使用 Vosk 提取音频文字
    3. 合并用户额外文本（如果有）
    4. 进行观点对冲分析

    Args:
        file: 上传的视频文件
        user_text: 可选的额外文本描述
        use_online: 是否使用联网百炼模式（默认False）
    """
    # 验证文件类型
    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.content_type}。请上传 MP4、MOV、AVI 格式的视频。"
        )

    temp_path = None
    try:
        # 获取文件后缀
        suffix_map = {
            "video/mp4": ".mp4",
            "video/quicktime": ".mov",
            "video/x-msvideo": ".avi",
            "video/webm": ".webm",
        }
        suffix = suffix_map.get(file.content_type, ".mp4")

        # 保存临时文件
        temp_path = save_upload_file(file, suffix=suffix)
        logger.info("视频文件已保存: {}", temp_path)

        # 提取视频文字
        video_result = VideoToTextResult()
        try:
            video_text = await extract_text_from_video_file(temp_path)
            video_result = VideoToTextResult(text=video_text)
        except FileNotFoundError as e:
            error_msg = str(e)
            if "ffmpeg" in error_msg:
                raise HTTPException(
                    status_code=500,
                    detail="视频处理失败：系统未安装 ffmpeg。请使用链接模式进行分析。"
                )
            elif "model" in error_msg.lower():
                raise HTTPException(
                    status_code=500,
                    detail="视频处理失败：语音识别模型未找到。请先下载 Vosk 模型。"
                )
            else:
                raise HTTPException(status_code=500, detail=f"视频处理失败: {error_msg}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"视频处理失败: {str(e)}")

        # 检查转写结果
        if video_result.is_empty:
            raise HTTPException(
                status_code=422,
                detail="视频未检测到有效语音内容，可能视频无声音或声音过小。请尝试使用链接模式。"
            )

        # 合并文本
        final_text = video_text
        if user_text and user_text.strip():
            final_text = f"{video_text}\n\n用户补充：{user_text}"

        # 进行分析（根据模式选择）
        if use_online:
            result = await analyze_with_bailian_online(final_text)
        else:
            result = await analyze_bias_from_text(final_text)

        # 添加视频转写信息到结果
        result["video_info"] = {
            "transcribed_length": len(video_text),
            "user_text_added": bool(user_text and user_text.strip()),
        }
        result["analysis_mode"] = "online" if use_online else "offline"

        return result

    finally:
        # 清理临时文件
        if temp_path:
            cleanup_temp_file(temp_path)
