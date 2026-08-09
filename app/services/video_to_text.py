"""
视频文件转文字服务
封装 Vosk 离线语音识别，将视频文件的音频转为文字。
"""

import os
import tempfile
from typing import Optional

from app.services.emotion_analyzer import extract_video_text
from app.utils.logger import logger


async def extract_text_from_video_file(video_path: str) -> str:
    """
    从视频文件提取音频并转写为文字。

    Args:
        video_path: 视频文件的本地路径

    Returns:
        str: 转写后的文字内容

    Raises:
        FileNotFoundError: ffmpeg 或 Vosk 模型未安装
        Exception: 转写过程中发生其他错误
    """
    try:
        text = await extract_video_text(video_path)
        logger.info("视频转写完成，长度: {} 字符", len(text))
        return text
    except FileNotFoundError as e:
        logger.error("视频转写失败 - 缺少依赖: {}", e)
        raise
    except Exception as e:
        logger.exception("视频转写失败: {}", e)
        raise


def save_upload_file(upload_file, suffix: str = ".mp4") -> str:
    """
    将上传的文件保存到临时目录。

    Args:
        upload_file: FastAPI UploadFile 对象
        suffix: 文件后缀名

    Returns:
        str: 临时文件路径
    """
    # 创建临时文件
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    try:
        # 直接同步读取文件内容并写入
        # UploadFile.file 是 SpooledTemporaryFile，支持直接 read()
        content = upload_file.file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        # 重置文件指针，以便后续可能的使用
        upload_file.file.seek(0)
        logger.info("临时文件已保存: {}", temp_path)
        return temp_path
    except Exception as e:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise e


def cleanup_temp_file(file_path: str) -> None:
    """
    删除临时文件。

    Args:
        file_path: 临时文件路径
    """
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug("临时文件已删除: {}", file_path)
    except Exception as e:
        logger.warning("删除临时文件失败: {} - {}", file_path, e)


class VideoToTextResult:
    """视频转文字结果封装"""

    def __init__(self, text: str = "", error: Optional[str] = None):
        self.text = text
        self.error = error
        self.success = error is None

    @property
    def is_empty(self) -> bool:
        return len(self.text) < 10

    def to_dict(self):
        return {
            "text": self.text,
            "error": self.error,
            "success": self.success,
            "is_empty": self.is_empty,
            "text_length": len(self.text)
        }
