from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import (
    auth, bias, care, chat, critical_thinking, enterprise,
    history, hotspot, legal, media_reliability, monitor,
    notifications, plan, predict, profile, report, search,
    settings, simulation, videos,
)
from app.database import Base, engine
from app.utils.logger import logger  # noqa: F401

Path("logs").mkdir(exist_ok=True, parents=True)
Path("uploads").mkdir(exist_ok=True, parents=True)

app = FastAPI(
    title="知舆 API",
    description="自媒体舆论检测与情绪管理系统 — 个人审辩思维 + 企业舆情中台",
    version="2.0.0",
)

# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Demo放宽限制
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================
# 数据库迁移辅助函数
# ============================================================

async def ensure_column_exists(table: str, column: str, alter_sql: str) -> bool:
    """通用：检查表是否有某列，没有则执行 ALTER TABLE"""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            columns = [row[1] for row in result.fetchall()]
            if column not in columns:
                logger.info(f"检测到 {table} 表缺少 {column} 列，正在添加...")
                await conn.execute(text(alter_sql))
                logger.info(f"{column} 列添加成功")
                return True
            else:
                logger.info(f"{table} 表 {column} 列已存在")
                return False
    except Exception as e:
        logger.warning(f"检查/添加 {table}.{column} 列时出现异常（非致命）: {e}")
        return False


async def run_all_migrations():
    """启动时运行所有必要的数据库迁移"""
    migrations = [
        # video_analyses 表
        ("video_analyses", "category",
         "ALTER TABLE video_analyses ADD COLUMN category VARCHAR(50) DEFAULT '其他' NOT NULL"),
        # users 表 - 旧字段
        ("users", "phone",
         "ALTER TABLE users ADD COLUMN phone VARCHAR(20) UNIQUE"),
        ("users", "privacy_mode_default",
         "ALTER TABLE users ADD COLUMN privacy_mode_default INTEGER DEFAULT 0"),
        ("users", "notifications_enabled",
         "ALTER TABLE users ADD COLUMN notifications_enabled INTEGER DEFAULT 1"),
        ("users", "last_care_time",
         "ALTER TABLE users ADD COLUMN last_care_time TIMESTAMP"),
        # users 表 - 新字段（个人版/企业版）
        ("users", "user_type",
         "ALTER TABLE users ADD COLUMN user_type VARCHAR(20) DEFAULT 'personal'"),
        ("users", "subscription_tier",
         "ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free'"),
        ("users", "subscription_expiry",
         "ALTER TABLE users ADD COLUMN subscription_expiry TIMESTAMP"),
        ("users", "trial_started_at",
         "ALTER TABLE users ADD COLUMN trial_started_at TIMESTAMP"),
        ("users", "enterprise_brand",
         "ALTER TABLE users ADD COLUMN enterprise_brand VARCHAR(255)"),
    ]
    for table, column, sql in migrations:
        await ensure_column_exists(table, column, sql)


# ============================================================
# 启动事件
# ============================================================

@app.on_event("startup")
async def startup_event():
    """启动时创建表并运行迁移"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_all_migrations()
    logger.info("数据库初始化完成（v2.0 个人版/企业版）")


# ============================================================
# 路由注册
# ============================================================

app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(profile.router)
app.include_router(monitor.router)
app.include_router(hotspot.router)
app.include_router(settings.router)
app.include_router(care.router)
app.include_router(notifications.router)
app.include_router(bias.router)
app.include_router(media_reliability.router)
app.include_router(legal.router)
app.include_router(predict.router)
app.include_router(plan.router)
app.include_router(report.router)
app.include_router(search.router)
app.include_router(simulation.router)
app.include_router(enterprise.router)          # 企业版 API
app.include_router(critical_thinking.router)    # 审辩思维 API

# ============================================================
# 静态文件服务
# ============================================================

# 挂载 index_files 静态资源目录（前端 CDN fallback，目录存在才挂载）
index_files_dir = ROOT_DIR / "index_files"
if index_files_dir.exists():
    app.mount("/index_files", StaticFiles(directory=str(index_files_dir)), name="index_files")

# 挂载 static 静态资源目录（案例库 docx 文件等）
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static_files")

# 挂载 web/shared 共享前端资源
web_shared = ROOT_DIR / "web" / "shared"
if web_shared.exists():
    app.mount("/web/shared", StaticFiles(directory=str(web_shared)), name="web_shared")


# ============================================================
# 前端页面路由
# ============================================================

@app.get("/")
async def root():
    """主工作台（个人版审辩思维 + 原有全部功能）"""
    return FileResponse(str(ROOT_DIR / "web" / "landing.html"))


@app.get("/personal")
async def personal():
    """个人版 SPA"""
    personal_path = ROOT_DIR / "web" / "personal.html"
    if personal_path.exists():
        return FileResponse(str(personal_path))
    return FileResponse(str(ROOT_DIR / "web" / "landing.html"))


@app.get("/enterprise")
async def enterprise_page():
    """企业版 SPA"""
    enterprise_path = ROOT_DIR / "web" / "enterprise.html"
    if enterprise_path.exists():
        return FileResponse(str(enterprise_path))
    return FileResponse(str(ROOT_DIR / "web" / "landing.html"))


# ============================================================
# 案例下载
# ============================================================

@app.get("/api/download-case/{case_id}")
async def download_case(case_id: int):
    """下载舆情案例研究报告原始 docx 文件"""
    import os
    from fastapi import HTTPException

    folder = ROOT_DIR / "static" / "cases"
    case_map = {
        1: "霸王茶姬逆天公示",
        2: "格力某米剑指黑公关",
        3: "小鹏机器人深陷争议",
        4: "嘲讽打工人掉粉超百万",
    }
    keyword = case_map.get(case_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="案例不存在")

    matched = None
    for f in os.listdir(folder):
        if f.endswith('.docx') and keyword in f:
            matched = f
            break
    if not matched:
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=str(folder / matched),
        filename=matched,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


# ============================================================
# 健康检查
# ============================================================

@app.get("/health")
async def health_check(check_external: bool = False):
    """健康检查端点"""
    result: dict = {"status": "ok", "services": {}}
    if check_external:
        import httpx
        from app.config import settings

        if settings.metaso_api_key:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        settings.metaso_base_url,
                        headers={"Authorization": f"Bearer {settings.metaso_api_key}"},
                    )
                    result["services"]["metaso"] = {
                        "status": "reachable" if resp.status_code < 500 else "error",
                        "code": resp.status_code,
                    }
            except Exception as e:
                result["services"]["metaso"] = {"status": "unreachable", "error": str(e)}
        else:
            result["services"]["metaso"] = {"status": "not_configured"}

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.mirofish_base_url}/")
                result["services"]["mirofish"] = {
                    "status": "reachable" if resp.status_code < 500 else "error",
                    "code": resp.status_code,
                }
        except Exception as e:
            result["services"]["mirofish"] = {"status": "unreachable", "error": str(e)}

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
