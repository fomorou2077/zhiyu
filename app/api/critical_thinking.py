"""
个人版审辩思维 API 路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/critical-thinking", tags=["审辩思维"])


# ---------- 事实核查 ----------

class FactCheckRequest(BaseModel):
    claim: str


@router.post("/fact-check")
async def fact_check(
    body: FactCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对声明进行事实核查"""
    from app.services.fact_checker import verify_claim
    result = await verify_claim(body.claim)
    # 保存到数据库
    from app.models.critical_thinking import ClaimVerification
    record = ClaimVerification(
        user_id=current_user.id,
        claim_text=body.claim,
        verdict=result.get("verdict", "unverified"),
        confidence=result.get("confidence", 0.0),
        evidence_items=result.get("evidence_items", []),
        reasoning=result.get("reasoning", ""),
        search_results_used=result.get("search_results_used", 0),
    )
    db.add(record)
    await db.commit()
    return result


# ---------- 逻辑谬误识别 ----------

class FallacyRequest(BaseModel):
    text: str


@router.post("/fallacy/detect")
async def detect_fallacy(
    body: FallacyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检测文本中的逻辑谬误"""
    from app.services.fallacy_detector import detect_fallacies
    result = await detect_fallacies(body.text)
    from app.models.critical_thinking import LogicalFallacy
    record = LogicalFallacy(
        user_id=current_user.id,
        input_text=body.text,
        fallacies_found=result.get("fallacies_found", []),
        overall_assessment=result.get("overall_assessment", ""),
    )
    db.add(record)
    await db.commit()
    return result


# ---------- 多语言交叉验证 ----------

class CrossVerifyRequest(BaseModel):
    claim: str
    languages: list = ["zh", "en"]


@router.post("/cross-verify")
async def cross_verify(
    body: CrossVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """多语言信源交叉验证"""
    from app.services.cross_verifier import cross_verify_claim
    result = await cross_verify_claim(body.claim, body.languages)
    from app.models.critical_thinking import CrossVerification
    record = CrossVerification(
        user_id=current_user.id,
        claim_text=body.claim,
        languages_searched=body.languages,
        sources_by_language=result.get("sources_by_language", {}),
        consensus_level=result.get("consensus_level", "no_data"),
    )
    db.add(record)
    await db.commit()
    return result


# ---------- 立场光谱 ----------

class SpectrumRequest(BaseModel):
    topic: str


@router.post("/spectrum/analyze")
async def analyze_spectrum(
    body: SpectrumRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成立场光谱"""
    from app.services.spectrum_analyzer import analyze_spectrum
    result = await analyze_spectrum(body.topic)
    from app.models.critical_thinking import PositionSpectrum
    record = PositionSpectrum(
        user_id=current_user.id,
        topic=body.topic,
        positions=result.get("positions", []),
        spectrum_visualization=result.get("spectrum_visualization", {}),
    )
    db.add(record)
    await db.commit()
    return result


# ---------- 深度伪造检测 ----------

class DeepfakeImageRequest(BaseModel):
    file_name: str = ""


class DeepfakeVideoRequest(BaseModel):
    file_name: str = ""


@router.post("/deepfake/detect-image")
async def detect_deepfake_image(
    body: DeepfakeImageRequest = DeepfakeImageRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """图片深度伪造检测（Demo预设数据，待接入阿里云内容安全）"""
    from app.services.deepfake_detector import detect_image
    result = await detect_image(file_name=body.file_name or None)
    # 保存记录
    from app.models.critical_thinking import DeepfakeDetection
    record = DeepfakeDetection(
        user_id=current_user.id,
        media_type="image",
        file_name=body.file_name or "unknown",
        analysis_result=result,
    )
    db.add(record)
    await db.commit()
    return result


@router.post("/deepfake/detect-video")
async def detect_deepfake_video(
    body: DeepfakeVideoRequest = DeepfakeVideoRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """视频深度伪造检测（Demo预设数据，待接入阿里云内容安全）"""
    from app.services.deepfake_detector import detect_video
    result = await detect_video(file_name=body.file_name or None)
    # 保存记录
    from app.models.critical_thinking import DeepfakeDetection
    record = DeepfakeDetection(
        user_id=current_user.id,
        media_type="video",
        file_name=body.file_name or "unknown",
        analysis_result=result,
    )
    db.add(record)
    await db.commit()
    return result


# ---------- 历史 ----------

@router.get("/history")
async def get_critical_thinking_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审辩分析历史（从数据库真实查询）"""
    from sqlalchemy import select, desc
    from app.models.critical_thinking import (
        ClaimVerification, LogicalFallacy, CrossVerification, PositionSpectrum
    )

    # 事实核查历史
    fc_result = await db.execute(
        select(ClaimVerification)
        .where(ClaimVerification.user_id == current_user.id)
        .order_by(desc(ClaimVerification.created_at))
        .limit(20)
    )
    fact_checks = [
        {
            "id": r.id,
            "claim_text": r.claim_text[:200],
            "verdict": r.verdict,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in fc_result.scalars().all()
    ]

    # 逻辑谬误历史
    fal_result = await db.execute(
        select(LogicalFallacy)
        .where(LogicalFallacy.user_id == current_user.id)
        .order_by(desc(LogicalFallacy.created_at))
        .limit(20)
    )
    fallacies = [
        {
            "id": r.id,
            "input_text": r.input_text[:200],
            "fallacies_found": len(r.fallacies_found or []),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in fal_result.scalars().all()
    ]

    # 交叉验证历史
    cv_result = await db.execute(
        select(CrossVerification)
        .where(CrossVerification.user_id == current_user.id)
        .order_by(desc(CrossVerification.created_at))
        .limit(20)
    )
    cross_verifications = [
        {
            "id": r.id,
            "claim_text": r.claim_text[:200],
            "consensus_level": r.consensus_level,
            "languages_searched": r.languages_searched,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in cv_result.scalars().all()
    ]

    # 立场光谱历史
    sp_result = await db.execute(
        select(PositionSpectrum)
        .where(PositionSpectrum.user_id == current_user.id)
        .order_by(desc(PositionSpectrum.created_at))
        .limit(20)
    )
    spectrums = [
        {
            "id": r.id,
            "topic": r.topic,
            "positions_count": len(r.positions or []),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in sp_result.scalars().all()
    ]

    return {
        "fact_checks": fact_checks,
        "fallacies": fallacies,
        "cross_verifications": cross_verifications,
        "spectrums": spectrums,
    }
