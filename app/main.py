from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import auth, chat, history, profile, videos, monitor, hotspot, settings, care, notifications, bias, media_reliability, legal, predict, plan, report, search, simulation
from app.database import Base, engine
from app.utils.logger import logger  # noqa: F401

Path("logs").mkdir(exist_ok=True, parents=True)
Path("uploads").mkdir(exist_ok=True, parents=True)

app = FastAPI(
    title="知舆 API",
    description="自媒体舆论检测与情绪管理系统",
    version="1.0.0",
)

# 获取项目根目录（run.py 所在目录）
ROOT_DIR = Path(__file__).parent.parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def ensure_category_column():
    """
    检查 video_analyses 表是否存在 category 列，
    若不存在则自动添加。
    """
    try:
        async with engine.begin() as conn:
            # 检查列是否存在
            result = await conn.execute(
                text("PRAGMA table_info(video_analyses)")
            )
            columns = [row[1] for row in result.fetchall()]

            if "category" not in columns:
                logger.info("检测到 video_analyses 表缺少 category 列，正在添加...")
                await conn.execute(
                    text("ALTER TABLE video_analyses ADD COLUMN category VARCHAR(50) DEFAULT '其他' NOT NULL")
                )
                logger.info("category 列添加成功")
            else:
                logger.info("video_analyses 表 category 列已存在")
    except Exception as e:
        logger.warning("检查/添加 category 列时出现异常（非致命）: {}", e)


async def ensure_phone_column():
    """
    检查 users 表是否存在 phone 列，
    若不存在则自动添加。
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]

            if "phone" not in columns:
                logger.info("检测到 users 表缺少 phone 列，正在添加...")
                await conn.execute(
                    text("ALTER TABLE users ADD COLUMN phone VARCHAR(20) UNIQUE")
                )
                logger.info("phone 列添加成功")
            else:
                logger.info("users 表 phone 列已存在")
    except Exception as e:
        logger.warning("检查/添加 phone 列时出现异常（非致命）: {}", e)


async def ensure_user_settings_columns():
    """
    检查 users 表是否存在隐私模式和推送设置列，
    若不存在则自动添加。
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]

            new_columns = [
                ("privacy_mode_default", "ALTER TABLE users ADD COLUMN privacy_mode_default INTEGER DEFAULT 0"),
                ("notifications_enabled", "ALTER TABLE users ADD COLUMN notifications_enabled INTEGER DEFAULT 1"),
                ("last_care_time", "ALTER TABLE users ADD COLUMN last_care_time TIMESTAMP"),
            ]

            for col_name, alter_sql in new_columns:
                if col_name not in columns:
                    await conn.execute(text(alter_sql))
                    logger.info(f"已添加 {col_name} 列到 users 表")
                else:
                    logger.info(f"users 表 {col_name} 列已存在")
    except Exception as e:
        logger.warning("检查/添加用户设置列时出现异常（非致命）: {}", e)


@app.on_event("startup")
async def startup_event():
    """
    启动时自动创建数据库表（若不存在），
    并检查并添加必要的字段。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 检查并添加 category 列
    await ensure_category_column()
    # 检查并添加 phone 列
    await ensure_phone_column()
    # 检查并添加用户设置列
    await ensure_user_settings_columns()

    logger.info("数据库初始化完成")


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
app.include_router(bias.router)  # 观点对冲分析
app.include_router(media_reliability.router)  # 媒体可靠性分级
app.include_router(legal.router)  # 法律证据包导出
app.include_router(predict.router)  # 热度预测
app.include_router(plan.router)  # 策划分析
app.include_router(report.router)  # 一键生成报告
app.include_router(search.router)  # 秘塔搜索
app.include_router(simulation.router)  # MIROFISH 模拟

# 挂载 index_files 静态资源目录
app.mount("/index_files", StaticFiles(directory=str(ROOT_DIR / "index_files")), name="static")

# 挂载 static 静态资源目录（用于案例库等）
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static_files")


@app.get("/api/download-case/{case_id}")
async def download_case(case_id: int):
    """
    下载舆情案例研究报告原始 docx 文件
    case_id: 1=霸王茶姬, 2=格力小米, 3=小鹏机器人, 4=嘲讽打工人
    """
    import os
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    ROOT = Path(__file__).parent.parent
    folder = ROOT / "新建文件夹"

    # 映射表：case_id -> 原始 docx 文件名关键字
    case_map = {
        1: "霸王茶姬逆天公示",
        2: "格力某米剑指黑公关",
        3: "小鹏机器人深陷争议",
        4: "嘲讽打工人掉粉超百万",
    }

    keyword = case_map.get(case_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="案例不存在")

    # 在新建文件夹中搜索匹配文件
    matched = None
    for f in os.listdir(folder):
        if f.endswith('.docx') and keyword in f:
            matched = f
            break

    if not matched:
        raise HTTPException(status_code=404, detail="文件不存在")

    file_path = folder / matched

    # 使用 FileResponse 自动处理中文文件名，避免手动设置 Content-Disposition 头导致的编码错误
    return FileResponse(
        path=str(file_path),
        filename=matched,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@app.get("/")
async def root():
    """根路径返回 desktop.html"""
    return FileResponse(str(ROOT_DIR / "desktop" / "desktop.html"))


@app.get("/health")
async def health_check(check_external: bool = False):
    """
    健康检查端点。

    参数:
        check_external: 是否检查外部服务连通性（默认否，避免拖慢响应）
    """
    result: dict = {"status": "ok", "services": {}}

    if check_external:
        import httpx
        from app.config import settings

        # 检查秘塔 API
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
                result["services"]["metaso"] = {
                    "status": "unreachable",
                    "error": str(e),
                }
        else:
            result["services"]["metaso"] = {"status": "not_configured"}

        # 检查 MIROFISH
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.mirofish_base_url}/")
                result["services"]["mirofish"] = {
                    "status": "reachable" if resp.status_code < 500 else "error",
                    "code": resp.status_code,
                }
        except Exception as e:
            result["services"]["mirofish"] = {
                "status": "unreachable",
                "error": str(e),
            }

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
