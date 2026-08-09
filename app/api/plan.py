"""
策划分析 API 路由
提供策划方案的舆情风险评估功能
"""

from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from app.services.file_processor import process_uploaded_files
from app.services.plan_analyzer import analyze_plan, extract_overall_risk_level
from app.utils.logger import logger

router = APIRouter(prefix="/plan", tags=["策划分析"])


# 方案类型选项
PLAN_TYPES = [
    "营销活动",
    "广告文案",
    "公关声明",
    "发布会",
    "品牌合作",
    "社交媒体内容",
    "其他"
]


@router.post("/analyze")
async def analyze_plan_endpoint(
    plan_name: str = Form(..., description="方案名称"),
    plan_type: str = Form(..., description="方案类型"),
    target_audience: Optional[str] = Form(None, description="目标受众"),
    content_description: Optional[str] = Form(None, description="方案详细内容描述"),
    files: Optional[List[UploadFile]] = File(None, description="上传的附件文件")
):
    """
    分析策划方案的舆情风险

    - 合并用户输入的描述和从上传文件中提取的文本
    - 调用大模型生成10维度结构化风险评估报告
    - 返回完整的分析报告

    支持的文件格式: docx, pdf, 图片(jpg, png等)
    """
    logger.info("收到策划分析请求: {}", plan_name)

    # 验证必填字段
    if not plan_name or not plan_name.strip():
        raise HTTPException(status_code=400, detail="方案名称不能为空")

    if plan_type not in PLAN_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的方案类型。可选: {', '.join(PLAN_TYPES)}"
        )

    try:
        # 1. 合并文本内容
        combined_text = content_description or ""

        if files:
            logger.info("处理 {} 个上传文件", len(files))
            # 过滤有效的文件
            valid_files = [f for f in files if f and f.filename]
            if valid_files:
                extracted_text = await process_uploaded_files(valid_files)
                if extracted_text:
                    combined_text += "\n\n===== 以下是从附件中提取的内容 =====\n\n" + extracted_text

        # 2. 调用大模型生成分析报告
        logger.info("开始调用大模型分析...")
        report = await analyze_plan(
            plan_name=plan_name.strip(),
            plan_type=plan_type,
            target_audience=target_audience,
            content_text=combined_text
        )

        # 3. 提取风险等级
        risk_level = extract_overall_risk_level(report)

        logger.info("策划分析完成: {}, 风险等级: {}", plan_name, risk_level)

        # 4. 返回结果
        return {
            "status": "success",
            "plan_name": plan_name,
            "plan_type": plan_type,
            "risk_level": risk_level,
            "report": report
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("策划分析失败: {}", plan_name)
        raise HTTPException(
            status_code=500,
            detail=f"分析失败: {str(e)}"
        )


@router.get("/types")
async def get_plan_types():
    """获取支持的方案类型列表"""
    return {
        "types": PLAN_TYPES
    }


@router.post("/extract-text")
async def extract_text_from_files(
    files: List[UploadFile] = File(..., description="要提取文本的文件")
):
    """
    仅提取文件文本（不进行分析）

    用于预览上传文件的内容
    """
    logger.info("收到文件文本提取请求: {} 个文件", len(files))

    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    try:
        extracted_text = await process_uploaded_files(files)

        return {
            "status": "success",
            "file_count": len(files),
            "text_length": len(extracted_text),
            "text": extracted_text[:5000]  # 限制返回长度
        }

    except Exception as e:
        logger.exception("文件文本提取失败")
        raise HTTPException(
            status_code=500,
            detail=f"文本提取失败: {str(e)}"
        )
