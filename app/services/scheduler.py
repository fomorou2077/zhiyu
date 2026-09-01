"""
定时任务调度服务 - Scheduler
每小时轮询监测关键词，生成监测快照
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import logger

# 简单的内存调度器状态
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None
_last_run: Optional[datetime] = None
_run_count: int = 0


async def run_monitoring_cycle(db_factory):
    """
    执行一次监测轮询：
    1. 查找所有企业版用户的监测关键词
    2. 对每个关键词生成模拟监测快照
    """
    global _last_run, _run_count
    from app.models.enterprise import EnterpriseBrand, MonitoringSnapshot

    try:
        async with db_factory() as db:
            # 查找所有设置了监测关键词的企业品牌
            result = await db.execute(
                select(EnterpriseBrand).where(EnterpriseBrand.monitored_keywords.isnot(None))
            )
            brands = result.scalars().all()

            snapshot_count = 0
            for brand in brands:
                keywords = brand.monitored_keywords or []
                if not keywords:
                    continue

                for keyword in keywords[:5]:  # 每个品牌最多处理5个关键词
                    for platform in ["微博", "抖音", "小红书", "B站"]:
                        # 生成模拟监测数据
                        mentions = random.randint(0, 50)
                        snapshot = MonitoringSnapshot(
                            user_id=brand.user_id,
                            snapshot_time=datetime.utcnow(),
                            platform=platform,
                            keyword=keyword,
                            mentions_count=mentions,
                            sentiment_summary={
                                "positive": random.randint(10, 60),
                                "neutral": random.randint(10, 40),
                                "negative": random.randint(0, 20),
                            },
                            hot_posts=[
                                {
                                    "title": f"关于{keyword}的讨论",
                                    "url": "#",
                                    "engagement": random.randint(100, 5000),
                                }
                                for _ in range(random.randint(0, 3))
                            ],
                        )
                        db.add(snapshot)
                        snapshot_count += 1

            await db.commit()
            _last_run = datetime.utcnow()
            _run_count += 1
            logger.info("监测轮询完成 (第{}次): 处理了{}个品牌，生成了{}条快照",
                       _run_count, len(brands), snapshot_count)

    except Exception as e:
        logger.exception("监测轮询异常: {}", e)


async def scheduler_loop(db_factory, interval_seconds: int = 3600):
    """调度器主循环，每隔 interval_seconds 秒执行一次监测"""
    global _scheduler_running
    logger.info("企业版监测调度器已启动，间隔={}秒", interval_seconds)
    _scheduler_running = True

    while _scheduler_running:
        try:
            await run_monitoring_cycle(db_factory)
        except Exception as e:
            logger.exception("调度器循环异常: {}", e)

        # 等待下一次执行
        await asyncio.sleep(interval_seconds)


def start_scheduler(db_factory, interval_seconds: int = 3600):
    """启动定时监测调度器"""
    global _scheduler_task, _scheduler_running

    if _scheduler_task and not _scheduler_task.done():
        logger.warning("调度器已在运行中")
        return _scheduler_task

    _scheduler_task = asyncio.create_task(scheduler_loop(db_factory, interval_seconds))
    logger.info("调度器任务已创建")
    return _scheduler_task


def stop_scheduler():
    """停止定时监测调度器"""
    global _scheduler_running, _scheduler_task
    _scheduler_running = False
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("调度器已停止")


def get_scheduler_status() -> dict:
    """获取调度器运行状态"""
    global _scheduler_running, _last_run, _run_count
    return {
        "running": _scheduler_running,
        "last_run": _last_run.isoformat() if _last_run else None,
        "run_count": _run_count,
        "interval_hours": 1,
    }
