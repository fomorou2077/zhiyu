from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.video_analysis import VideoAnalysis
from app.schemas.video import VideoAnalysisResponse
from app.services.emotion_analyzer import analyze_video_emotion, extract_video_text
from app.services.baichuan_service import analyze_emotion, generate_tailored_suggestions, analyze_counter_arguments
from app.services.file_service import get_original_filename, save_upload_file
from app.utils.logger import logger
from app.utils.security import decode_access_token as decode_token

router = APIRouter(prefix="/videos", tags=["videos"])


def get_user_id_from_token(authorization: str) -> int:
    """从 Authorization header 中提取 user_id（失败返回1作为默认值）"""
    if not authorization:
        return 1

    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        if payload and payload.get("user_id"):
            return int(payload["user_id"])
        return 1
    except Exception:
        return 1


def _build_simulation_result(reason: str) -> dict:
    """当无法从视频提取有效文本时，返回一个有意义的模拟分析结果。"""
    import random
    rng = random.Random(hash(reason) % 1000)

    emotions = {
        "joy": round(rng.uniform(3, 8), 1),
        "sadness": round(rng.uniform(1, 5), 1),
        "anger": round(rng.uniform(1, 4), 1),
        "calm": round(rng.uniform(3, 7), 1),
        "anxiety": round(rng.uniform(2, 6), 1),
        "expectation": round(rng.uniform(3, 8), 1),
    }
    risk_score = round(
        emotions["anger"] * 1.5
        + emotions["anxiety"] * 1.3
        + emotions["sadness"] * 1.0
        - emotions["joy"] * 0.5
        - emotions["calm"] * 0.5
    )
    risk_score = max(0, min(100, risk_score + 30))

    logger.info("兜底分析结果: risk_score={}, reason={}", risk_score, reason)
    return {
        "emotions": emotions,
        "risk_score": risk_score,
        "keywords": ["视频内容", "语音分析"],
        "suggestions": f"该视频未能提取有效语音内容（{reason}），分析结果为模拟参考值，建议上传有声音的视频以获得更准确的分析。",
        "category": "其他",
    }


async def _analyze_text_only(file_path: str) -> dict:
    """纯文本分析：Vosk 转写 + 百炼情绪分析。"""
    video_text = ""
    try:
        video_text = await extract_video_text(file_path)
    except FileNotFoundError as e:
        logger.warning("视频文本提取失败（ffmpeg 或模型缺失）: {}，使用兜底分析", e)
        return _build_simulation_result("ffmpeg或模型缺失")

    logger.info("视频文本长度: {}, 预览: {}", len(video_text), video_text[:100])

    if not video_text or len(video_text) < 10:
        logger.warning("视频未检测到有效语音内容，使用兜底模拟分析")
        return _build_simulation_result("视频无声音轨道")

    analysis = await analyze_emotion(video_text)
    logger.info("百炼情绪分析完成: risk_score={}, category={}",
                analysis.get("risk_score"), analysis.get("category"))
    return analysis


@router.post("/upload", response_model=VideoAnalysisResponse)
async def upload_video(
    file: UploadFile = File(...),
    use_multimodal: bool = Query(False),
    privacy_mode: bool = Query(False),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_id = get_user_id_from_token(authorization)

        logger.info("=" * 50)
        logger.info("开始处理视频上传: filename={}, use_multimodal={}, privacy_mode={}",
                    file.filename, use_multimodal, privacy_mode)

        # 1. 保存文件
        file_path = await save_upload_file(file)
        logger.info("视频文件已保存: {}", file_path)

        # 2. 根据模式选择分析路径
        if use_multimodal:
            logger.info("使用多模态分析模式")
            try:
                from app.services.qwen_multimodal import analyze_video_multimodal_advanced
                analysis = await analyze_video_multimodal_advanced(file_path)
                logger.info("百炼多模态分析完成: risk_score={}", analysis.get("risk_score"))
            except ImportError as e:
                logger.warning("多模态模块导入失败: {}，回退到文本分析", e)
                analysis = await _analyze_text_only(file_path)
        else:
            logger.info("使用文本分析模式")
            analysis = await _analyze_text_only(file_path)

        # 3. 生成建议
        logger.info("生成建议...")
        suggestions_detail = await generate_tailored_suggestions(
            risk_score=analysis["risk_score"],
            emotions=analysis["emotions"],
            keywords=analysis["keywords"],
            category=analysis.get("category", "其他"),
        )
        logger.info("建议生成完成")

        # 4. 对抗预演分析（仅在非隐私模式下启用）
        counter_analysis = None
        if not privacy_mode:
            try:
                # 构建用于对抗分析的文本（使用更多内容）
                analysis_keywords = analysis.get('keywords', [])
                analysis_suggestions = analysis.get('suggestions', '')
                analysis_category = analysis.get('category', '其他')

                # 如果关键词太少，使用完整文本
                if len(analysis_keywords) < 2 and video_text:
                    text_for_analysis = f"这是一个关于{analysis_category}的视频内容。视频描述：{video_text[:500]}"
                else:
                    text_for_analysis = f"内容类别：{analysis_category}。关键词：{', '.join(analysis_keywords)}。分析建议：{analysis_suggestions}"

                logger.info("开始对抗预演分析，文本长度: {}", len(text_for_analysis))
                counter_analysis = await analyze_counter_arguments(text_for_analysis)
                logger.info("对抗预演分析完成")
            except Exception as e:
                logger.warning("对抗预演分析失败: {}", e)
                counter_analysis = None

        # 5. 持久化
        if not privacy_mode:
            record = VideoAnalysis(
                user_id=user_id,
                file_name=get_original_filename(file),
                file_path=file_path,
                emotions=analysis["emotions"],
                risk_score=analysis["risk_score"],
                keywords=analysis["keywords"],
                suggestions=analysis["suggestions"],
                category=analysis.get("category", "其他"),
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            logger.info("分析结果已保存到数据库: id={}", record.id)
            return VideoAnalysisResponse(
                id=record.id,
                file_name=record.file_name,
                emotions=record.emotions,
                risk_score=record.risk_score,
                keywords=record.keywords,
                suggestions=record.suggestions,
                suggestions_detail=suggestions_detail,
                category=record.category,
                counter_analysis=counter_analysis,
                created_at=record.created_at,
            )
        else:
            logger.info("隐私模式，分析结果不保存数据库")
            return VideoAnalysisResponse(
                id=0,
                file_name=get_original_filename(file),
                emotions=analysis["emotions"],
                risk_score=analysis["risk_score"],
                keywords=analysis["keywords"],
                suggestions=analysis["suggestions"],
                suggestions_detail=suggestions_detail,
                category=analysis.get("category", "其他"),
                counter_analysis=counter_analysis,
                created_at=None,
            )

    except FileNotFoundError as e:
        logger.error("文件操作失败: {}", e)
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("视频上传或分析失败: {}", e)
        raise HTTPException(status_code=500, detail=f"视频分析失败: {str(e)}")
