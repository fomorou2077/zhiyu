"""
企业版 API 路由
"""
import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_enterprise_user, get_current_user
from app.models.enterprise import (
    AlertRule, AuditLog, AutoResponse, CompetitorMonitor,
    DashboardConfig, EnterpriseBrand, MonitoringSnapshot,
    ReportArchive, SpreadTrace,
)
from app.models.user import User
from app.utils.logger import logger

router = APIRouter(prefix="/api/enterprise", tags=["企业版"])


# ============================================================
# 仪表盘
# ============================================================

@router.get("/monitor/dashboard")
async def get_dashboard(current_user: User = Depends(get_current_user)):
    """获取企业版监控仪表盘数据（Demo预设数据，基于品牌名匹配场景）"""
    from app.services.demo_data import get_dashboard_preset

    brand_name = current_user.enterprise_brand or "品牌"
    preset = get_dashboard_preset(brand_name)
    preset["brand"] = brand_name  # 覆盖为实际品牌名
    return preset


# ============================================================
# 监测关键词
# ============================================================

class KeywordUpdate(BaseModel):
    keywords: List[str] = []


@router.get("/monitor/keywords")
async def get_keywords(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前监测关键词"""
    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    return {"keywords": brand.monitored_keywords if brand else []}


@router.post("/monitor/keywords")
async def update_keywords(
    body: KeywordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新监测关键词"""
    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if not brand:
        brand = EnterpriseBrand(
            user_id=current_user.id,
            brand_name=current_user.enterprise_brand or "未命名品牌",
            monitored_keywords=body.keywords,
        )
        db.add(brand)
    else:
        brand.monitored_keywords = body.keywords
    await db.commit()
    return {"success": True, "keywords": body.keywords}


@router.post("/monitor/smart-expand")
async def smart_expand_keywords(
    body: KeywordUpdate,
    current_user: User = Depends(get_current_user),
):
    """AI智能扩展关键词（调用大模型）"""
    base = body.keywords if body.keywords else [current_user.enterprise_brand or "品牌"]
    try:
        from app.services.baichuan_service import chat_with_ai

        prompt = f"""你是品牌舆情监测专家。用户当前监测的关键词是：{', '.join(base)}。
请基于这些关键词，扩展出15-20个相关监测关键词，覆盖以下维度：
1. 品牌变体（简称、昵称、英文名）
2. 产品相关（核心产品、新品、型号）
3. 高管/代言人
4. 负面关联（投诉、维权、曝光、骗局）
5. 竞品对比（vs/对比/哪个好）
6. 行业话题

以JSON数组格式返回，只返回关键词列表：
["关键词1", "关键词2", ...]"""

        messages = [{"role": "user", "content": prompt}]
        response = await chat_with_ai(messages, model="qwen-turbo")
        response = response.strip()
        if "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
            if response.startswith("json"):
                response = response[4:].strip()
        import json
        expanded = json.loads(response)
        if isinstance(expanded, list) and len(expanded) > 0:
            all_kw = list(set(list(base) + expanded))
            return {"keywords": all_kw, "ai_expanded": True}
    except Exception:
        pass

    # LLM不可用时的降级方案
    suffixes = ["评价", "投诉", "测评", "对比", "口碑", "体验", "价格", "质量", "服务", "新品"]
    expanded = []
    for kw in base:
        expanded.append(kw)
        for s in suffixes:
            expanded.append(f"{kw}{s}")
    return {"keywords": list(set(expanded)), "ai_expanded": False}


# ============================================================
# 传播追踪
# ============================================================

@router.get("/monitor/spread-trace/{incident_id}")
async def get_spread_trace(
    incident_id: int,
    current_user: User = Depends(get_current_user),
):
    """获取事件的传播路径网络图数据"""
    from app.services.spread_tracer import trace_spread, analyze_spread_pattern

    keywords = [current_user.enterprise_brand or "品牌事件"]
    trace_data = await trace_spread(incident_id, keywords)
    pattern = await analyze_spread_pattern(incident_id)
    return {**trace_data, "pattern_analysis": pattern}


# ============================================================
# 竞品监测
# ============================================================

class CompetitorAdd(BaseModel):
    competitor_name: str
    platform: Optional[str] = None
    notes: Optional[str] = None


@router.get("/monitor/competitors")
async def get_competitors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取竞品监测数据"""
    import random
    # 从品牌设置中获取竞品列表
    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    competitors = brand.monitored_competitors if brand else []

    # 为每个竞品生成mock数据
    data = []
    for comp in competitors:
        data.append({
            "name": comp,
            "metrics": {
                "mention_volume": random.randint(100, 5000),
                "sentiment_positive": random.randint(30, 70),
                "sentiment_negative": random.randint(5, 25),
                "engagement_rate": round(random.uniform(1.0, 8.0), 1),
            },
            "top_platforms": random.sample(["微博", "抖音", "小红书", "B站"], k=min(3, 4)),
            "last_updated": datetime.now().isoformat(),
        })
    return {"competitors": data, "total": len(data)}


@router.post("/monitor/competitors")
async def add_competitor(
    body: CompetitorAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加竞品监测"""
    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if not brand:
        brand = EnterpriseBrand(
            user_id=current_user.id,
            brand_name=current_user.enterprise_brand or "未命名品牌",
            monitored_competitors=[body.competitor_name],
        )
        db.add(brand)
    else:
        competitors = list(brand.monitored_competitors or [])
        if body.competitor_name not in competitors:
            competitors.append(body.competitor_name)
            brand.monitored_competitors = competitors
    await db.commit()
    return {"success": True, "competitors": brand.monitored_competitors}


@router.delete("/monitor/competitors/{competitor_name}")
async def remove_competitor(
    competitor_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除竞品"""
    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if brand and brand.monitored_competitors:
        brand.monitored_competitors = [
            c for c in brand.monitored_competitors if c != competitor_name
        ]
        await db.commit()
    return {"success": True}


# ============================================================
# 预警规则
# ============================================================

class AlertRuleCreate(BaseModel):
    name: str
    keywords: List[str] = []
    sentiment_threshold: float = 0.3
    platforms: List[str] = ["weibo", "douyin", "xiaohongshu"]
    enabled: bool = True


@router.get("/alerts/rules")
async def get_alert_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取预警规则列表"""
    result = await db.execute(
        select(AlertRule)
        .where(AlertRule.user_id == current_user.id)
        .order_by(desc(AlertRule.created_at))
    )
    rules = result.scalars().all()
    return {
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "keywords": r.keywords,
                "sentiment_threshold": r.sentiment_threshold,
                "platforms": r.platforms,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rules
        ],
        "total": len(rules),
    }


@router.post("/alerts/rules")
async def create_alert_rule(
    body: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建预警规则"""
    rule = AlertRule(
        user_id=current_user.id,
        name=body.name,
        keywords=body.keywords,
        sentiment_threshold=body.sentiment_threshold,
        platforms=body.platforms,
        enabled=body.enabled,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    logger.info("用户 {} 创建预警规则: {}", current_user.username, body.name)
    return {"success": True, "id": rule.id, "name": rule.name}


@router.put("/alerts/rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    body: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新预警规则"""
    result = await db.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == current_user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    rule.name = body.name
    rule.keywords = body.keywords
    rule.sentiment_threshold = body.sentiment_threshold
    rule.platforms = body.platforms
    rule.enabled = body.enabled
    await db.commit()
    return {"success": True}


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除预警规则"""
    result = await db.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == current_user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    await db.delete(rule)
    await db.commit()
    return {"success": True}


# ============================================================
# 自动回应生成
# ============================================================

class ResponseGenerateRequest(BaseModel):
    incident_description: str
    response_type: str = "official_statement"  # official_statement|media_talking_points|internal_alignment|kol_outreach|legal_notice
    incident_severity: str = "medium"  # low|medium|high|critical
    key_facts: List[str] = []


class ResponseGenerateAllRequest(BaseModel):
    incident_description: str
    incident_severity: str = "medium"
    key_facts: List[str] = []


@router.post("/response/generate")
async def generate_response(
    body: ResponseGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成单种类型的回应"""
    from app.services.auto_responder import generate_response as gen

    brand_name = current_user.enterprise_brand or "我司"
    result = await gen(
        incident_description=body.incident_description,
        brand_name=brand_name,
        response_type=body.response_type,
        incident_severity=body.incident_severity,
        key_facts=body.key_facts,
    )

    # 保存到数据库
    record = AutoResponse(
        user_id=current_user.id,
        incident_id=0,
        response_type=body.response_type,
        content=str(result),
    )
    db.add(record)
    await db.commit()

    return result


@router.post("/response/generate-all")
async def generate_all_responses(
    body: ResponseGenerateAllRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一次性生成全部5种回应类型"""
    from app.services.auto_responder import generate_all_responses as gen_all

    brand_name = current_user.enterprise_brand or "我司"
    results = await gen_all(
        incident_description=body.incident_description,
        brand_name=brand_name,
        incident_severity=body.incident_severity,
        key_facts=body.key_facts,
    )

    # 保存每种类型
    for resp_type, content in results["responses"].items():
        record = AutoResponse(
            user_id=current_user.id,
            incident_id=0,
            response_type=resp_type,
            content=str(content),
        )
        db.add(record)
    await db.commit()

    return results


@router.get("/response/history")
async def get_response_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取回应生成历史"""
    result = await db.execute(
        select(AutoResponse)
        .where(AutoResponse.user_id == current_user.id)
        .order_by(desc(AutoResponse.generated_at))
        .limit(20)
    )
    records = result.scalars().all()
    return {
        "responses": [
            {
                "id": r.id,
                "response_type": r.response_type,
                "incident_id": r.incident_id,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "preview": (r.content or "")[:200],
            }
            for r in records
        ]
    }


# ============================================================
# 报告生成
# ============================================================

class ReportGenerateRequest(BaseModel):
    report_type: str = "daily"  # daily|weekly|monthly|incident|competitor|plan_risk|post_event
    title: Optional[str] = None
    data: dict = {}
    output_format: str = "docx"  # docx|pdf|html


@router.post("/reports/generate")
async def generate_report(
    body: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成舆情报告"""
    from app.services.report_exporter import generate_report as gen_report

    title = body.title or f"{current_user.enterprise_brand or '品牌'}舆情{body.report_type}报告"
    result = await gen_report(
        report_type=body.report_type,
        title=title,
        data=body.data,
        user_id=current_user.id,
        output_format=body.output_format,
    )

    # 保存归档记录
    record = ReportArchive(
        user_id=current_user.id,
        report_type=body.report_type,
        title=title,
        file_path=result["file_path"],
        file_format=result["format"],
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {**result, "archive_id": record.id}


@router.get("/reports/archives")
async def get_report_archives(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取报告归档列表"""
    result = await db.execute(
        select(ReportArchive)
        .where(ReportArchive.user_id == current_user.id)
        .order_by(desc(ReportArchive.generated_at))
        .limit(50)
    )
    archives = result.scalars().all()
    return {
        "reports": [
            {
                "id": r.id,
                "report_type": r.report_type,
                "title": r.title,
                "file_format": r.file_format,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            }
            for r in archives
        ]
    }


@router.get("/reports/download/{archive_id}")
async def download_report(
    archive_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """下载报告文件"""
    result = await db.execute(
        select(ReportArchive).where(
            ReportArchive.id == archive_id,
            ReportArchive.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="报告不存在")
    if not record.file_path or not os.path.exists(record.file_path):
        raise HTTPException(status_code=404, detail="报告文件不存在，请重新生成")

    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "html": "text/html",
    }
    return FileResponse(
        path=record.file_path,
        filename=f"{record.title}.{record.file_format}",
        media_type=media_types.get(record.file_format, "application/octet-stream"),
    )


# ============================================================
# 仪表盘配置
# ============================================================

class DashboardConfigUpdate(BaseModel):
    layout: list = []  # 组件布局配置数组


@router.get("/dashboard/config")
async def get_dashboard_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """读取仪表盘布局配置"""
    result = await db.execute(
        select(DashboardConfig).where(DashboardConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    return {
        "layout": config.layout if config else [
            {"id": "heat_trend", "type": "chart", "x": 0, "y": 0, "w": 8, "h": 4, "title": "热度趋势"},
            {"id": "sentiment_pie", "type": "chart", "x": 8, "y": 0, "w": 4, "h": 4, "title": "情绪分布"},
            {"id": "keyword_cloud", "type": "chart", "x": 0, "y": 4, "w": 6, "h": 4, "title": "关键词云"},
            {"id": "recent_mentions", "type": "list", "x": 6, "y": 4, "w": 6, "h": 4, "title": "最新提及"},
        ]
    }


@router.put("/dashboard/config")
async def update_dashboard_config(
    body: DashboardConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存仪表盘布局配置"""
    result = await db.execute(
        select(DashboardConfig).where(DashboardConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        config = DashboardConfig(user_id=current_user.id, layout=body.layout)
        db.add(config)
    else:
        config.layout = body.layout
    await db.commit()
    return {"success": True, "layout": body.layout}


# ============================================================
# 品牌管理
# ============================================================

class BrandUpdate(BaseModel):
    brand_name: str
    industry: Optional[str] = None
    monitored_competitors: List[str] = []


@router.get("/brand")
async def get_brand(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取企业品牌信息"""
    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if brand:
        return {
            "brand_name": brand.brand_name,
            "industry": brand.industry,
            "monitored_keywords": brand.monitored_keywords or [],
            "monitored_competitors": brand.monitored_competitors or [],
        }
    return {
        "brand_name": current_user.enterprise_brand or "",
        "industry": "",
        "monitored_keywords": [],
        "monitored_competitors": [],
    }


@router.put("/brand")
async def update_brand(
    body: BrandUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新企业品牌信息"""
    current_user.enterprise_brand = body.brand_name

    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if not brand:
        brand = EnterpriseBrand(
            user_id=current_user.id,
            brand_name=body.brand_name,
            industry=body.industry,
            monitored_competitors=body.monitored_competitors,
        )
        db.add(brand)
    else:
        brand.brand_name = body.brand_name
        brand.industry = body.industry
        brand.monitored_competitors = body.monitored_competitors
    await db.commit()
    return {"success": True, "brand_name": body.brand_name}


# ============================================================
# 订阅与升级
# ============================================================

class UpgradeRequest(BaseModel):
    brand_name: str
    industry: Optional[str] = None
    reason: Optional[str] = None


@router.get("/subscription")
async def get_subscription(current_user: User = Depends(get_current_user)):
    """获取订阅状态"""
    return {
        "user_type": current_user.user_type,
        "subscription_tier": current_user.subscription_tier,
        "subscription_expiry": current_user.subscription_expiry.isoformat()
        if current_user.subscription_expiry else None,
        "trial_started_at": current_user.trial_started_at.isoformat()
        if current_user.trial_started_at else None,
        "is_trial": (
            current_user.trial_started_at is not None
            and current_user.subscription_expiry
            and current_user.subscription_expiry > datetime.utcnow()
        ),
    }


@router.post("/upgrade")
async def upgrade_to_enterprise(
    body: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """个人版升级为企业版（Demo简化流程）"""
    if current_user.user_type == "enterprise":
        return {"message": "您已是企业版用户", "user_type": "enterprise"}

    current_user.user_type = "enterprise"
    current_user.enterprise_brand = body.brand_name
    current_user.subscription_tier = "enterprise"
    current_user.trial_started_at = datetime.utcnow()
    current_user.subscription_expiry = datetime.utcnow() + timedelta(days=30)

    # 创建品牌记录
    result = await db.execute(
        select(EnterpriseBrand).where(EnterpriseBrand.user_id == current_user.id)
    )
    brand = result.scalar_one_or_none()
    if not brand:
        brand = EnterpriseBrand(
            user_id=current_user.id,
            brand_name=body.brand_name,
            industry=body.industry,
        )
        db.add(brand)

    await db.commit()
    logger.info("用户 {} 升级为企业版，品牌={}", current_user.username, body.brand_name)
    return {
        "success": True,
        "message": "已升级为企业版，享受30天免费试用",
        "user_type": "enterprise",
        "subscription_tier": "enterprise",
        "trial_days_remaining": 30,
    }


# ============================================================
# 监测快照
# ============================================================

@router.get("/monitor/snapshots")
async def get_monitoring_snapshots(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
):
    """获取定时监测快照历史"""
    result = await db.execute(
        select(MonitoringSnapshot)
        .where(MonitoringSnapshot.user_id == current_user.id)
        .order_by(desc(MonitoringSnapshot.snapshot_time))
        .limit(limit)
    )
    snapshots = result.scalars().all()
    return {
        "snapshots": [
            {
                "id": s.id,
                "snapshot_time": s.snapshot_time.isoformat() if s.snapshot_time else None,
                "platform": s.platform,
                "keyword": s.keyword,
                "mentions_count": s.mentions_count,
                "sentiment_summary": s.sentiment_summary,
                "hot_posts": s.hot_posts,
            }
            for s in snapshots
        ]
    }


# ============================================================
# 调度器状态
# ============================================================

@router.get("/scheduler/status")
async def get_scheduler_status(current_user: User = Depends(get_current_enterprise_user)):
    """获取监测调度器运行状态"""
    from app.services.scheduler import get_scheduler_status as get_status
    return get_status()


# ============================================================
# 审计日志
# ============================================================

@router.get("/audit-logs")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
):
    """获取操作审计日志"""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": len(logs),
    }


def _record_audit_log(db, user_id: int, action: str, resource_type: str = "", resource_id: int = None, details: str = None):
    """记录审计日志的辅助函数"""
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    db.add(log)


# ============================================================
# 数据管理
# ============================================================

@router.post("/data/export")
async def export_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出用户所有数据为JSON文件"""
    import json, os
    from fastapi.responses import FileResponse
    from sqlalchemy import select
    from app.models.video_analysis import VideoAnalysis
    from app.models.monitor import MonitorRecord
    from app.models.critical_thinking import (
        ClaimVerification, LogicalFallacy, CrossVerification, PositionSpectrum, DeepfakeDetection
    )

    user_id = current_user.id

    # 收集所有用户数据
    va = (await db.execute(select(VideoAnalysis).where(VideoAnalysis.user_id == user_id))).scalars().all()
    mr = (await db.execute(select(MonitorRecord).where(MonitorRecord.user_id == user_id))).scalars().all()
    fc = (await db.execute(select(ClaimVerification).where(ClaimVerification.user_id == user_id))).scalars().all()
    fl = (await db.execute(select(LogicalFallacy).where(LogicalFallacy.user_id == user_id))).scalars().all()
    cv = (await db.execute(select(CrossVerification).where(CrossVerification.user_id == user_id))).scalars().all()
    ps = (await db.execute(select(PositionSpectrum).where(PositionSpectrum.user_id == user_id))).scalars().all()
    df = (await db.execute(select(DeepfakeDetection).where(DeepfakeDetection.user_id == user_id))).scalars().all()

    export_data = {
        "export_time": datetime.utcnow().isoformat(),
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "user_type": current_user.user_type,
            "subscription_tier": current_user.subscription_tier,
        },
        "video_analyses": [
            {"id": r.id, "file_name": r.file_name, "risk_score": r.risk_score,
             "category": r.category, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in va
        ],
        "monitor_records": [
            {"id": r.id, "platform": r.platform, "title": r.title,
             "risk_score": r.risk_score, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in mr
        ],
        "fact_checks": [
            {"id": r.id, "claim_text": r.claim_text, "verdict": r.verdict, "confidence": r.confidence,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in fc
        ],
        "fallacy_detections": [
            {"id": r.id, "input_text": r.input_text, "fallacies_count": len(r.fallacies_found or []),
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in fl
        ],
        "cross_verifications": [
            {"id": r.id, "claim_text": r.claim_text, "consensus_level": r.consensus_level,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in cv
        ],
        "position_spectrums": [
            {"id": r.id, "topic": r.topic, "positions_count": len(r.positions or []),
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in ps
        ],
        "deepfake_detections": [
            {"id": r.id, "media_type": r.media_type, "file_name": r.file_name,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in df
        ],
        "total_records": len(va) + len(mr) + len(fc) + len(fl) + len(cv) + len(ps) + len(df),
    }

    # 写入导出文件
    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"zhiyu_export_{current_user.id}_{timestamp}.json"
    file_path = export_dir / file_name
    file_path.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")

    _record_audit_log(db, current_user.id, "data_export", "account")

    return {
        "success": True,
        "message": f"数据导出成功，共 {export_data['total_records']} 条记录",
        "file_name": file_name,
        "total_records": export_data["total_records"],
        "download_url": f"/api/enterprise/data/download/{file_name}",
    }


@router.get("/data/download/{file_name}")
async def download_export_file(file_name: str, current_user: User = Depends(get_current_user)):
    """下载导出的数据文件"""
    file_path = Path("exports") / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已过期")
    return FileResponse(
        path=str(file_path),
        filename=file_name,
        media_type="application/json",
    )


@router.post("/data/delete")
async def delete_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    confirm: str = "NO",
):
    """
    删除账号所有数据。
    需要请求体携带 {"confirm": "DELETE_MY_DATA"} 作为二次确认。
    """
    if confirm != "DELETE_MY_DATA":
        return {
            "success": False,
            "message": "请在请求体中添加 \"confirm\": \"DELETE_MY_DATA\" 以确认删除",
            "warning": "此操作不可逆！将永久删除您账号下的所有数据",
        }

    from sqlalchemy import delete
    from app.models.video_analysis import VideoAnalysis
    from app.models.monitor import MonitorRecord
    from app.models.critical_thinking import (
        ClaimVerification, LogicalFallacy, CrossVerification, PositionSpectrum, DeepfakeDetection
    )
    from app.models.enterprise import (
        EnterpriseBrand, AlertRule, AutoResponse, MonitoringSnapshot,
        DashboardConfig, ReportArchive, AuditLog, SpreadTrace, CompetitorMonitor,
    )

    user_id = current_user.id
    tables = [
        VideoAnalysis, MonitorRecord,
        ClaimVerification, LogicalFallacy, CrossVerification, PositionSpectrum, DeepfakeDetection,
        EnterpriseBrand, AlertRule, AutoResponse, MonitoringSnapshot,
        DashboardConfig, ReportArchive, AuditLog, SpreadTrace, CompetitorMonitor,
    ]

    deleted_counts = {}
    for table in tables:
        result = await db.execute(delete(table).where(table.user_id == user_id))
        deleted_counts[table.__tablename__] = result.rowcount

    # 记录删除操作（写完后立即commit，因后续会删掉audit_log表自己的记录）
    _record_audit_log(db, user_id, "data_delete_confirmed", "account",
                      details=f"用户确认删除所有数据，涉及{len(tables)}张表")
    await db.commit()

    total = sum(deleted_counts.values())
    logger.warning("用户 {} 已删除所有数据，共 {} 条记录", current_user.username, total)

    return {
        "success": True,
        "message": f"所有数据已永久删除",
        "deleted_records": total,
        "details": {k: v for k, v in deleted_counts.items() if v > 0},
    }
