import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.utils.logger import logger

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

def _normalize_filename(name: str) -> str:
    """
    Windows/PowerShell 下部分客户端上传中文文件名可能出现乱码（如 cp936/gbk -> latin1）。
    这里做一次尽力而为的还原，失败则返回原值。
    """
    if not name:
        return name
    try:
        # 常见情况：客户端按本地编码发送，服务端当 latin1 解码，导致变成“²ôË®...”这种
        return name.encode("latin1").decode("gbk")
    except Exception:
        try:
            return name.encode("latin1").decode("utf-8")
        except Exception:
            return name


def validate_file(file: UploadFile):
    original_name = _normalize_filename(file.filename)
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(status_code=400, detail="不允许的文件类型: {}".format(ext))


async def save_upload_file(file: UploadFile) -> str:
    validate_file(file)
    original_name = _normalize_filename(file.filename)
    ext = os.path.splitext(original_name)[1].lower()
    new_filename = "{}{}".format(uuid.uuid4().hex, ext)
    file_path = UPLOAD_DIR / new_filename
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=400, detail="文件过大")
    with open(file_path, "wb") as f:
        f.write(content)
    logger.info("文件已保存: {}", file_path)
    return str(file_path)


def get_original_filename(file: UploadFile) -> str:
    """
    获取尽力还原后的原始文件名，用于入库/返回展示。
    """
    return _normalize_filename(file.filename)
