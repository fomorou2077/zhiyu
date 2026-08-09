from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """
    初始化数据库：创建所有表，并检查并添加 phone 列（如果不存在）。
    用于 SQLite 等不支持自动迁移的数据库。
    """
    from app.models.user import User
    from app.models.video_analysis import VideoAnalysis
    from app.models.monitor import MonitorRecord
    from app.models.chat_history import ChatHistory
    from app.models.emotion_profile import EmotionProfile

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 检查并添加 phone 列（如果使用 SQLite 且表已存在）
    if "sqlite" in settings.database_url:
        async with engine.begin() as conn:
            # 检查 users 表是否有 phone 列
            try:
                result = await conn.execute(text("PRAGMA table_info(users)"))
                columns = [row[1] for row in result.fetchall()]
                if "phone" not in columns:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20) UNIQUE"))
                    print("[数据库迁移] 已添加 phone 列到 users 表")
            except Exception as e:
                print(f"[数据库迁移] 检查 phone 列时出错（可能已存在）: {e}")
