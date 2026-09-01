# 知舆企业版 - 后端架构技术指南

## 一、现状评估

当前企业版后端（`app/api/enterprise.py` + `app/models/enterprise.py`）已有20个API端点、9张数据表、5套Demo预设数据。但存在以下核心问题：

| 问题 | 现状 | 影响 |
|------|------|------|
| 数据来源 | 全部硬编码Demo数据 | 无真实舆情数据 |
| AI调用 | 仅百川API(qwen-turbo)做关键词扩展 | 情感分析/报告生成/回应生成均为假数据 |
| 实时性 | 无WebSocket/SSE推送 | 预警无法实时通知 |
| 数据采集 | 无爬虫/API接入 | 无法从微博/抖音等平台获取数据 |
| 存储 | SQLite单文件 | 无法支撑百万级数据查询 |
| 认证 | 无企业级权限控制 | 所有企业用户共享API |

---

## 二、目标架构总览

```
                              +-----------------------------+
                              |      负载均衡 (Nginx)        |
                              +-----------------------------+
                                |        |         |
                   +------------+   +----+----+   +---------+
                   | FastAPI    |   | FastAPI  |   | FastAPI |
                   | (Web API)  |   | (Admin)  |   | (Public)|
                   +-----+------+   +----+-----+   +----+----+
                         |               |               |
              +----------+---------------+---------------+--------+
              |                   消息队列 (RabbitMQ / Redis)        |
              +--+---------+---------+---------+---------+--------+
                 |         |         |         |         |
          +------+--+ +---+----+ +--+---+ +---+----+ +---+------+
          | 爬虫调度 | | 情感   | | 预警  | | 报告   | | AI 回应  |
          | Worker  | | Worker | |Worker | | Worker | | Worker   |
          +------+--+ +---+----+ +--+---+ +---+----+ +---+------+
                 |         |         |         |         |
          +------+---------+---------+---------+---------+------+
          |                   数据层                              |
          |  PostgreSQL + Redis + Elasticsearch + MinIO          |
          +------------------------------------------------------+
          |                   外部服务                             |
          |  微博API | 抖音API | 小红书 | 知乎 | 百川 | 其他LLM   |
          +------------------------------------------------------+
```

---

## 三、数据采集层（最关键的缺失）

### 3.1 多渠道数据源

```
数据源架构：

  +-------------+     +-------------+     +-------------+
  | 平台官方API  |     | 第三方数据   |     | RSS/爬虫     |
  | (微博/抖音) |     | (新榜/清博) |     | (新闻/论坛) |
  +------+------+     +------+------+     +------+------+
         |                   |                   |
         +-------------------+-------------------+
                             |
                     +-------v--------+
                     | 数据标准化层    |
                     | (统一Schema)   |
                     +-------+--------+
                             |
                     +-------v--------+
                     | 消息队列 Topic  |
                     | raw_mentions    |
                     +----------------+
```

### 3.2 统一数据Schema

```python
# 无论来源平台，统一为这个结构
class RawMention:
    mention_id: str          # 全局唯一ID
    platform: str            # weibo | douyin | xiaohongshu | zhihu | bilibili | kuaishou
    platform_post_id: str    # 原始平台帖子ID
    content_type: str        # text | image | video | article
    title: str               # 标题/正文前200字
    content: str             # 完整正文
    author_name: str         # 作者昵称
    author_followers: int    # 作者粉丝数
    publish_time: datetime   # 发布时间
    metrics: dict            # {likes, comments, shares, views}
    url: str                 # 原始链接
    captured_at: datetime    # 采集时间
    keyword_matched: list    # 命中了哪些监测关键词
```

### 3.3 采集策略

| 方式 | 适用平台 | 频率 | 成本 |
|------|---------|------|------|
| 官方API | 微博(商业API)、知乎 | 5-15分钟 | 按调用量计费 |
| 第三方数据商 | 抖音、小红书 | 实时推送 | 年费/包月 |
| 爬虫 | B站、论坛、新闻 | 30分钟 | 服务器+反爬 |
| RSS | 新闻媒体 | 15分钟 | 免费 |

**建议第一阶段**：先接入微博商业API + 新闻RSS，这是性价比最高的起步方案。

### 3.4 爬虫调度Worker

```python
# 伪代码
class CrawlerScheduler:
    async def run(self):
        for enterprise in active_enterprises:
            for keyword in enterprise.keywords:
                for platform in enterprise.platforms:
                    task = CrawlTask(
                        platform=platform,
                        keyword=keyword,
                        enterprise_id=enterprise.id,
                        interval_minutes=platform_config[platform].interval
                    )
                    await self.queue.enqueue(task)

# Worker消费
class CrawlWorker:
    async def process(self, task: CrawlTask):
        collector = PlatformCollectorFactory.get(task.platform)
        raw_data = await collector.search(task.keyword, task.since)
        standardized = self.normalize(raw_data, task.enterprise_id)
        await self.db.bulk_insert(standardized)
        await self.mq.publish("new_mentions", standardized)
```

---

## 四、数据处理与分析层

### 4.1 NLP Pipeline

```
raw_mentions (消息队列)
       |
+------v-------+
| 文本预处理     | → 去重、去噪、分词
+------+-------+
       |
+------v-------+
| 情感分析       | → 正面/中立/负面 + 置信度 + 情感强度
+------+-------+
       |
+------v-------+
| 实体识别       | → 品牌名、人名、地名、产品名
+------+-------+
       |
+------v-------+
| 话题聚类       | → 将相似内容聚合为话题
+------+-------+
       |
+------v-------+
| 意图分类       | → 投诉/咨询/赞美/建议/造谣
+------+-------+
       |
+------v-------+
| 存储 + 索引    | → PostgreSQL + Elasticsearch
+---------------+
```

### 4.2 LLM选型建议

| 任务 | 推荐模型 | 说明 |
|------|---------|------|
| 情感分析 | 微调BERT/RoBERTa | 速度快，成本低，可针对性训练 |
| 话题聚类 | text2vec + KMeans | 将相似文本向量化后聚类 |
| 报告生成 | Claude/DeepSeek | 需要长文本理解和生成能力 |
| 回应草稿 | Claude/GPT-4 | 需要高质量文案输出 |
| 关键词扩展 | DeepSeek-V3 | 性价比高 |

**关键架构**：LLM调用统一走 `LLMService` 抽象层，方便随时切换模型：

```python
class LLMService:
    """统一LLM调用接口"""
    def __init__(self, provider: str):
        self.provider = self._resolve_provider(provider)
    
    async def analyze_sentiment(self, text: str) -> SentimentResult: ...
    async def generate_report(self, data: ReportData) -> str: ...
    async def draft_response(self, incident: Incident, type: str) -> str: ...
    async def expand_keywords(self, seeds: list[str]) -> list[str]: ...
```

### 4.3 定时任务

```python
# Celery Beat 调度
SCHEDULE = {
    "crawl-all-platforms": {"task": "crawl_all", "schedule": crontab(minute="*/15")},
    "sentiment-batch": {"task": "batch_sentiment", "schedule": crontab(minute="*/5")},
    "alert-check": {"task": "check_alerts", "schedule": crontab(minute="*")},  # 每分钟
    "daily-report": {"task": "gen_daily_report", "schedule": crontab(hour=8, minute=0)},
    "weekly-report": {"task": "gen_weekly_report", "schedule": crontab(day_of_week=1, hour=8)},
    "data-cleanup": {"task": "cleanup_old_data", "schedule": crontab(hour=3, minute=0)},
}
```

---

## 五、实时预警引擎

这是企业版最核心的功能。当前版本完全缺失。

### 5.1 预警触发条件

```python
class AlertCondition:
    """一条预警规则可包含多个条件"""
    keyword_match: bool            # 关键词命中
    sentiment_threshold: float     # 负面占比超过X%
    volume_spike: float            # 声量突增超过X倍
    platform_specific: dict        # 特定平台的条件
    time_window: int               # 监测时间窗口(分钟)
    co_occurrence: list[str]       # 关键词共现要求
```

### 5.2 预警计算流程

```
每1分钟执行一次:

1. 从Elasticsearch查询最近N分钟的mention
2. 按企业/规则分组
3. 判断每条规则是否触发:
   - 关键词匹配 → 检查命中计数
   - 负面阈值 → 计算负面占比
   - 声量突增 → 对比历史基线(同比/环比)
4. 达到阈值的 → 生成Alert记录 + 推送通知
5. 已有alert的事件持续更新状态
```

### 5.3 预警分级

| 级别 | 条件示例 | 通知方式 |
|------|---------|---------|
| 危急 | 负面占比>50% 且 声量突增5倍 | 短信+电话+APP推送+邮件 |
| 高 | 负面占比>30% 或 声量突增3倍 | 短信+APP推送+邮件 |
| 中 | 负面占比>15% | APP推送+邮件 |
| 低 | 关键词命中但未达阈值 | 仅仪表盘显示 |

### 5.4 WebSocket实时推送

```python
# FastAPI WebSocket
@router.websocket("/ws/alerts")
async def alert_websocket(ws: WebSocket, token: str):
    user = verify_token(token)
    await ws.accept()
    # 订阅该用户的预警频道
    channel = f"enterprise:{user.enterprise_id}:alerts"
    await redis.subscribe(channel)
    
    async for message in redis.listen():
        await ws.send_json(message)
```

前端企业版目前是HTTP轮询，改为WebSocket后可实现真正的实时预警。

---

## 六、存储架构升级

### 6.1 从SQLite到PostgreSQL

| 数据 | 当前 | 目标 | 原因 |
|------|------|------|------|
| 用户/品牌/订阅 | SQLite | PostgreSQL | 多进程并发安全 |
| Mentions原始数据 | 不存在 | PostgreSQL (分区表) | 千万级数据量 |
| 时序统计数据 | 不存在 | TimescaleDB (PG扩展) | 高效时间范围查询 |
| 全文搜索 | 无 | Elasticsearch | 关键词检索 |
| 文件(报告PDF/图片) | 本地文件 | MinIO (S3兼容) | 分布式存储 |
| 缓存/会话/队列 | 无 | Redis | 高性能缓存+消息队列 |

### 6.2 核心表设计

```sql
-- mentions主表 (按月分区)
CREATE TABLE mentions (
    id BIGSERIAL,
    enterprise_id INTEGER NOT NULL,
    platform VARCHAR(20) NOT NULL,
    platform_post_id VARCHAR(100),
    title TEXT,
    content TEXT,
    author_name VARCHAR(200),
    author_followers INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    sentiment VARCHAR(10),          -- positive/neutral/negative
    sentiment_score FLOAT,          -- 0-1置信度
    entities JSONB,                 -- 命名实体
    keywords_matched JSONB,         -- 命中的监测词
    url TEXT,
    published_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    -- 索引
    PRIMARY KEY (id, published_at)
) PARTITION BY RANGE (published_at);

-- 时序统计 (TimescaleDB hypertable)
CREATE TABLE mention_stats (
    time TIMESTAMPTZ NOT NULL,
    enterprise_id INTEGER NOT NULL,
    keyword VARCHAR(100),
    platform VARCHAR(20),
    mention_count INTEGER,
    positive_count INTEGER,
    neutral_count INTEGER,
    negative_count INTEGER,
    UNIQUE(time, enterprise_id, keyword, platform)
);
SELECT create_hypertable('mention_stats', 'time');
```

### 6.3 Redis缓存策略

```python
# 热点数据缓存
CACHE_TTL = {
    "dashboard:{enterprise_id}": 60,        # 仪表盘数据 60秒
    "sentiment_trend:{enterprise_id}": 300,  # 情感趋势 5分钟
    "hot_topics:{enterprise_id}": 600,        # 热点话题 10分钟
    "alert_rules:{enterprise_id}": 3600,      # 预警规则 1小时
}
```

---

## 七、报告引擎

### 7.1 报告生成流程

```
用户请求 → 参数校验 → 数据聚合查询 → 
LLM生成正文 → 填入图表 → 渲染模板 → 
输出PDF/HTML/Word → 存储到MinIO → 返回下载链接
```

### 7.2 7种报告类型

| 类型 | 数据来源 | 更新频率 | LLM需求 |
|------|---------|---------|---------|
| 日报 | 过去24h mentions | 每日自动 | 摘要生成 |
| 周报 | 过去7天聚合 | 每周自动 | 趋势分析+建议 |
| 月报 | 过去30天聚合 | 每月自动 | 深度分析 |
| 事件专项 | 事件关联mentions | 手动触发 | 全链路复盘 |
| 竞品对比 | 多品牌mentions | 手动触发 | 对比分析 |
| 策划风险评估 | 方案文本 | 手动触发 | 10维风险分析 |
| 事后复盘 | 历史事件数据 | 手动触发 | 经验总结 |

### 7.3 报告模板引擎

使用Jinja2模板 + ECharts服务端渲染生成图表PNG，嵌入报告。

---

## 八、多租户与权限

### 8.1 租户隔离

```python
# 所有数据查询必须带 enterprise_id
class EnterpriseFilter:
    """中间件：自动注入enterprise_id过滤"""
    async def __call__(self, request, call_next):
        user = get_current_user(request)
        request.state.enterprise_id = user.enterprise_brand_id
        return await call_next(request)
```

### 8.2 角色权限

| 角色 | 权限范围 |
|------|---------|
| 超级管理员 | 全功能 + 用户管理 + 系统配置 |
| 品牌管理员 | 全功能 (限本品牌) |
| 分析师 | 查看仪表盘/预警/报告 + 导出 |
| 操作员 | 查看仪表盘/预警 + 关键词管理 |
| 只读 | 仅查看仪表盘 |

---

## 九、部署架构

### 9.1 最小生产部署

```
+--------------------------------------------------+
|  一台 8C16G 云服务器                               |
|                                                    |
|  Docker Compose:                                   |
|  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  |
|  │ FastAPI   │ │ Celery   │ │ Celery Beat        │ |
|  │ (4 workers)│ │ (4 workers)│ │ (1 scheduler)     │ |
|  └──────────┘ └──────────┘ └───────────────────┘  |
|  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  |
|  │ PostgreSQL│ │ Redis    │ │ Elasticsearch      │ |
|  │ +Timescale│ │          │ │                    │ |
|  └──────────┘ └──────────┘ └───────────────────┘  |
|  ┌──────────┐                                     |
|  │ Nginx    │ ← 反向代理 + SSL                     |
|  └──────────┘                                     |
+--------------------------------------------------+
月成本估算：~800-1500元 (国内云服务器)
```

### 9.2 扩展部署（100+企业客户）

```
+------------------+
|  CDN / WAF       |
+--------+---------+
         |
+--------v---------+
|  Nginx LB        |
+--+----+----+---+-+
   |    |    |   |
+--v-+ +v--+ +v-+ +v--+
|API | |API | |WS | |WS |   ← FastAPI × 4 (K8s)
+----+ +---+ +--+ +---+
         |
+--------v----------------------------------------+
|              Kafka / Pulsar                      |
+--+----+----+---+---+----+----+---+---+---------+
   |    |    |   |   |    |    |   |   |
+--v-+ +v--+ +v-+ +v-+ +v--+ +v--+ +v-+ +v--+
|爬虫| |NLP| |预警| |报告| |爬虫| |NLP| |预警| |报告| ← Celery Workers
+----+ +---+ +--+ +--+ +---+ +---+ +--+ +--+
         |
+--------v----------------------------------------+
|  PostgreSQL (主从) + Elasticsearch (集群) + Redis |
+-------------------------------------------------+
月成本估算：~5000-15000元
```

---

## 十、实施路线图

### 第一阶段：数据打通（2-4周）

1. 接入微博商业API + 新闻RSS
2. 搭建PostgreSQL + 数据采集Worker
3. 实现基础的mention存储和查询
4. 替换Demo数据为真实数据

### 第二阶段：智能分析（2-4周）

1. 集成情感分析模型(微调BERT或调用LLM)
2. 实现真实的话题聚类
3. 预警引擎实时计算
4. WebSocket推送

### 第三阶段：AI增强（2-3周）

1. Claude/DeepSeek接入报告生成
2. 自动回应草稿真实生成
3. 关键词智能扩展
4. 危机等级AI自动研判

### 第四阶段：企业级完善（2-4周）

1. 多租户权限体系
2. 报告导出PDF/Word
3. 数据看板自定义布局
4. 审计日志完善
5. 性能优化 + 压力测试

---

## 十一、关键文件改造清单

| 文件 | 当前状态 | 目标状态 |
|------|---------|---------|
| `app/models/enterprise.py` | 9个SQLite模型 | PostgreSQL模型 + 分区表Mentions |
| `app/api/enterprise.py` | 20个Demo端点 | 全部接入真实数据源 |
| `app/services/crawler.py` | 已有基础 | 多平台采集器 + 反爬策略 |
| `app/services/scheduler.py` | 每小时跑一次 | Celery Beat多任务调度 |
| `app/services/demo_data.py` | 当前唯一数据源 | 降级为fallback/测试用 |
| `app/services/alert_engine.py` | **不存在** | 新建：预警计算核心 |
| `app/services/report_gen.py` | **不存在** | 新建：报告生成引擎 |
| `app/services/sentiment.py` | **不存在** | 新建：情感分析服务 |
| `app/services/llm.py` | **不存在** | 新建：统一LLM调用层 |
| `docker-compose.yml` | **不存在** | 新建：生产部署配置 |
