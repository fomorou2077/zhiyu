"""
法律证据包导出 API
提供一键导出监测记录的法律证据包功能
"""

import io
import zipfile
import json
import csv
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.monitor import MonitorRecord
from app.models.video_analysis import VideoAnalysis

router = APIRouter(prefix="/legal", tags=["法律证据"])


@router.get("/export-evidence/{record_id}")
async def export_evidence(
    record_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    导出指定记录的法律证据包

    Args:
        record_id: 记录ID（可以是监测记录或视频分析记录）
        db: 数据库会话

    Returns:
        ZIP文件流，包含 metadata.json、comments.csv 和 README.txt
    """
    # 1. 查询监测记录
    result = await db.execute(
        select(MonitorRecord).where(MonitorRecord.id == record_id)
    )
    monitor = result.scalar_one_or_none()

    if monitor:
        title = monitor.title or "未命名"
        comments = monitor.comment_analysis.get("raw_comments", []) if monitor.comment_analysis else []
        created_at = monitor.created_at
        platform = monitor.platform or "未知平台"
        risk_score = monitor.risk_score
    else:
        # 尝试查询视频分析记录
        result2 = await db.execute(
            select(VideoAnalysis).where(VideoAnalysis.id == record_id)
        )
        video = result2.scalar_one_or_none()

        if not video:
            raise HTTPException(status_code=404, detail="记录不存在")

        title = video.file_name or "未命名视频"
        comments = []
        created_at = video.created_at
        platform = "视频分析"
        risk_score = video.risk_score

    # 2. 构建元数据
    metadata = {
        "record_id": record_id,
        "title": title,
        "platform": platform,
        "created_at": created_at.isoformat() if created_at else None,
        "risk_score": risk_score,
        "export_time": datetime.now().isoformat(),
        "export_version": "1.0",
        "system": "知舆 - 自媒体舆论检测与情绪管理系统"
    }

    # 3. 打包 ZIP 文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 元数据 JSON
        zf.writestr(
            "metadata.json",
            json.dumps(metadata, ensure_ascii=False, indent=2)
        )

        # 评论 CSV
        if comments:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["序号", "评论内容", "发布时间", "用户昵称", "点赞数", "情绪标签", "风险等级"])

            for idx, c in enumerate(comments, 1):
                writer.writerow([
                    idx,
                    c.get("text", ""),
                    c.get("time", ""),
                    c.get("user", ""),
                    c.get("likes", 0),
                    c.get("emotion", ""),
                    c.get("risk_level", "")
                ])
            zf.writestr("comments.csv", output.getvalue().encode("utf-8-sig"))
        else:
            zf.writestr(
                "comments.csv",
                "序号,评论内容,发布时间,用户昵称,点赞数,情绪标签,风险等级\n暂无评论数据,,,,\n".encode("utf-8-sig")
            )

        # 说明文件
        notice_content = f"""证据包说明文件
==================

本证据包由「知舆」系统自动生成。

基本信息：
- 记录ID: {record_id}
- 标题: {title}
- 平台: {platform}
- 监测时间: {created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else '未知'}
- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 风险评分: {risk_score or '未评估'}

文件说明：
- metadata.json: 原始记录元数据
- comments.csv: 评论数据（可用于法律举证）
- README.txt: 本说明文件

使用建议：
1. 本证据包可用于向平台投诉或法律举证
2. 建议结合原始视频/评论页面截图一并提交
3. 如需进一步分析，请联系专业人员

生成工具: 知舆 - 自媒体舆论检测与情绪管理系统
"""
        zf.writestr("README.txt", notice_content.encode("utf-8"))

    zip_buffer.seek(0)

    # 生成文件名
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:20]
    filename = f"evidence_{record_id}_{safe_title.replace(' ', '_')}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Content-Type": "application/zip"
        }
    )


@router.get("/evidence-info/{record_id}")
async def get_evidence_info(
    record_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取证据包预览信息（不下载）

    Args:
        record_id: 记录ID
        db: 数据库会话

    Returns:
        证据包基本信息
    """
    # 查询监测记录
    result = await db.execute(
        select(MonitorRecord).where(MonitorRecord.id == record_id)
    )
    monitor = result.scalar_one_or_none()

    if monitor:
        return {
            "exists": True,
            "record_type": "monitor",
            "title": monitor.title or "未命名",
            "platform": monitor.platform or "未知平台",
            "comment_count": len(monitor.comment_analysis.get("raw_comments", [])) if monitor.comment_analysis else 0,
            "created_at": monitor.created_at.isoformat() if monitor.created_at else None
        }

    # 尝试查询视频分析记录
    result2 = await db.execute(
        select(VideoAnalysis).where(VideoAnalysis.id == record_id)
    )
    video = result2.scalar_one_or_none()

    if video:
        return {
            "exists": True,
            "record_type": "video",
            "title": video.file_name or "未命名视频",
            "platform": "视频分析",
            "comment_count": 0,
            "created_at": video.created_at.isoformat() if video.created_at else None
        }

    raise HTTPException(status_code=404, detail="记录不存在")
