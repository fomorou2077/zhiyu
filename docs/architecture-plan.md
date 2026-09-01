# 知舆 ZhiYu 个人版/企业版 架构改造方案

## 一、背景与目标

将知舆从"单一舆情分析工具"改造为"个人审辩思维平台 + 企业品牌舆情中台"双版本。
- **同一代码库**，通过用户类型（`user_type`）切换功能和界面
- **DEMO版本**：点击即可在个人版/企业版之间切换，无需重新登录
- **目标用户**：个人版 = 创作者/普通用户（批判性思考）；企业版 = 品牌方公关部

---

## 二、功能归属决策

| 功能 | 归属 | 说明 |
|------|------|------|
| 视频情绪分析 | 个人版 | 核心审辩工具 |
| 热度预测 | 双版本 | 个人创作者 + 企业品牌监测 |
| 观点对冲 (Bias) | 个人版 | 核心审辩工具 |
| AI对话「知知」 | 个人版 | 关怀助手 |
| 多平台监测 | 企业版 | 核心功能 |
| 热点数据 | 双版本 | 共享 |
| 策划分析 (Plan) | 企业版 | 核心，增强A/B对比 |
| 报告生成 | 双版本 | 不同报告类型 |
| 媒体可靠性评级 | 个人版 | 核心审辩工具 |
| 法律证据 | 个人版 | 个人维权 |
| 秘塔搜索 | 双版本 | 共享 |
| MIROFISH推演 | 企业版 | 仅文档展示 |
| 舆情案例库 | 双版本 | 不同案例侧重 |
| 事实核查 | **个人版新增** | 参考MITA |
| 逻辑谬误识别 | **个人版新增** | 参考MITA |
| 多语言信源交叉验证 | **个人版新增** | 参考MITA |
| 深度伪造检测 | **个人版新增** | Demo占位 |
| 立场光谱可视化 | **个人版新增** | 观点分布图 |
| 实时预警 | **企业版新增** | 每小时轮询 |
| 传播追踪 | **企业版新增** | 网络图可视化 |
| 自动回应生成 | **企业版新增** | 5种模板 |
| 竞品监测 | **企业版新增** | 基础CRUD+mock |
| 监控仪表盘 | **企业版新增** | 可配置组件 |
| 审计日志 | **企业版新增** | 关键操作记录 |

---

## 三、实施步骤

### 阶段1：认证体系重构（基础工程，第1-2天）

**1.1 User 模型扩展** (`app/models/user.py`)
- 新增字段：`user_type` (personal/enterprise)、`subscription_tier` (free/basic/pro/enterprise)、`subscription_expiry`、`trial_started_at`、`enterprise_brand`

**1.2 创建统一认证依赖** (`app/dependencies.py` - 新文件)
- `get_current_user` → 从 Bearer token 解析 user_id，返回 User 对象
- `get_current_enterprise_user` → 要求 `user_type == "enterprise"`
- `get_current_personal_user` → 个人版（企业版用户也可访问）

**1.3 修复所有端点**
- `/auth/me` → 使用 `Depends(get_current_user)`，返回真实用户数据含 `user_type`
- `/auth/login` → JWT payload 中增加 `user_type`
- `/auth/register` → 默认 `user_type=personal`
- `history.py` → 替换 `user_id=1` 为 `current_user.id`
- `monitor.py` → 替换 `user_id=1` 为 `current_user.id`
- `chat.py` → 替换默认 `user_id: int = 1`
- `profile.py` → 替换 `user_id: int = Query(1)`
- `settings.py`、`notifications.py`、`care.py` → 用 `Depends(get_current_user)` 替换手动 token 提取

**1.4 版本切换接口**
- `POST /auth/switch-version` → 允许用户在前端切换展示版本（DEMO特性）

### 阶段2：新数据模型（第3天）

**2.1 企业版模型** (`app/models/enterprise.py` - 新文件)
- `EnterpriseBrand`：品牌信息、监测关键词、竞品列表
- `Subscription`：订阅状态、套餐、试用期
- `AlertRule`：预警规则（关键词、阈值、平台）
- `SpreadTrace`：传播节点和边
- `AutoResponse`：自动回应草稿
- `CompetitorMonitor`：竞品数据快照
- `MonitoringSnapshot`：定时监测快照
- `DashboardConfig`：仪表盘布局配置
- `ReportArchive`：报告归档
- `AuditLog`：操作审计

**2.2 个人版模型** (`app/models/critical_thinking.py` - 新文件)
- `ClaimVerification`：事实核查结果
- `LogicalFallacy`：逻辑谬误识别结果
- `CrossVerification`：多语言交叉验证结果
- `DeepfakeDetection`：深度伪造检测记录
- `PositionSpectrum`：立场光谱分析

### 阶段3：新 API 与服务（第4-7天）

**3.1 企业版 API** (`app/api/enterprise.py` - 新文件)
```
/api/enterprise/
  GET    monitor/dashboard          → 仪表盘所有数据
  POST   monitor/keywords           → 管理监测关键词
  POST   monitor/smart-expand       → AI智能关键词扩展
  GET    monitor/spread-trace/{id}  → 传播路径网络图
  POST   monitor/competitors        → 添加竞品监测
  GET    monitor/competitors        → 竞品数据
  
  GET    alerts/rules               → 预警规则列表
  POST   alerts/rules               → 创建预警规则
  
  POST   response/generate          → 生成5种回应类型
  GET    response/history           → 回应历史
  
  POST   reports/generate           → 生成各类报告
  GET    reports/archives           → 报告归档
  GET    reports/download/{id}      → 下载DOC/PDF
  
  GET    dashboard/config           → 读取仪表盘布局
  PUT    dashboard/config           → 保存仪表盘布局
  
  GET    brand                      → 企业品牌信息
  PUT    brand                      → 更新品牌
  
  POST   upgrade                    → 个人升级企业(提交材料)
  GET    subscription               → 订阅状态
  
  POST   data/export                → 导出全部数据
  POST   data/delete                → 删除账号数据
  
  GET    audit-logs                 → 审计日志
```

**3.2 个人版审辩 API** (`app/api/critical_thinking.py` - 新文件)
```
/api/critical-thinking/
  POST   fact-check                  → 事实核查
  POST   fallacy/detect             → 逻辑谬误识别
  POST   cross-verify               → 多语言信源交叉验证
  POST   spectrum/analyze           → 立场光谱分析
  POST   deepfake/detect-image      → 图片深度伪造检测(占位)
  POST   deepfake/detect-video      → 视频深度伪造检测(占位)
  GET    history                     → 审辩分析历史
```

**3.3 新服务文件** (`app/services/` 下新增)
- `fact_checker.py` → LLM+搜索的事实核查
- `fallacy_detector.py` → 逻辑谬误识别
- `cross_verifier.py` → 多语言交叉验证
- `auto_responder.py` → 5种企业回应模板生成
- `spread_tracer.py` → 传播路径分析
- `report_exporter.py` → DOC/PDF生成
- `scheduler.py` → 每小时监测轮询

**3.4 路由注册** (`app/main.py`)
- 注册 `enterprise_router` → `/api/enterprise`
- 注册 `critical_thinking_router` → `/api/critical-thinking`
- 添加路由级访问控制（企业版路由用 `get_current_enterprise_user`）
- 添加前端新页面路由：`/enterprise` → enterprise.html, `/personal` → personal.html, `/` → landing.html

### 阶段4：前端改造（第8-12天）

**4.1 目录结构**
```
web/
  landing.html            → 版本选择首页
  personal.html           → 个人版SPA（从desktop.html提取）
  enterprise.html         → 企业版SPA（全新）
  shared/
    css/
      theme.css           → 主题变量（提取自desktop.html）
      components.css      → 共享组件样式
    js/
      api-client.js       → 统一API调用（相对URL）
      store.js            → 用户状态管理
    components/
      auth-modal.js       → 登录注册模态框
      owl-chat.js         → 知知AI对话抽屉
      version-switcher.js → 版本切换按钮
```

**4.2 关键前端改动**
- 所有 API_URL 从硬编码 `http://localhost:8000` 改为空字符串 `''` （相对路径）
- `api-client.js`：自动从 localStorage 读取 token，处理 401/402/403
- `landing.html`：选择"个人版"/"企业版"卡片，跳转到对应SPA
- 右上角版本切换按钮：DEMO中点击即可在两个UI之间切换

**4.3 个人版前端导航**
```
首页 → 热度预测 → 事实核查 → 逻辑谬误识别 → 信源交叉验证 
→ 深度伪造检测 → 观点对冲 → 媒体可靠性 → 视频情绪分析 → 历史记录 → 个人档案 → 设置
```

**4.4 企业版前端导航**
```
监控大盘 → 实时预警 → 监测管理 → 传播追踪 → 竞品监测 
→ 策划分析 → 自动回应 → 报告中心 → 审计日志 → 设置
```

**4.5 企业版仪表盘**（可配置组件，客户自选）
- 舆情热度趋势图（ECharts 折线）
- 正负面情绪饼图（ECharts 饼图）
- 关键词云（ECharts wordCloud）
- 传播节点网络图（ECharts graph）
- 地域分布热力图（ECharts map）
- 最新提及列表

### 阶段5：静态文件服务（`app/main.py` 修改）

```python
# 服务新版前端
@app.get("/")
async def root():
    return FileResponse(ROOT_DIR / "web" / "landing.html")

@app.get("/personal")
async def personal():
    return FileResponse(ROOT_DIR / "web" / "personal.html")

@app.get("/enterprise")
async def enterprise():
    return FileResponse(ROOT_DIR / "web" / "enterprise.html")

# 挂载共享资源
app.mount("/web/shared", StaticFiles(directory=ROOT_DIR / "web" / "shared"), name="shared")
```

### 阶段6：合并与清理（第13天）

- 废弃 Flask `predict_app.py`，功能已由 FastAPI `/predict/ai-predict` 覆盖
- 删除 `start_predict.bat` 或标记废弃
- `desktop/desktop.html` 保留作为参考，不再作为主入口
- 更新 `README.md`

---

## 四、实施优先级

### P0（必须有，Demo核心）— 前7天
1. ✅ 认证体系重构（user_type + 统一依赖 + 修复硬编码）
2. ✅ User 模型扩展 + 迁移
3. ✅ 版本选择首页 landing.html
4. ✅ 企业版仪表盘（基础3个图表+demo数据）
5. ✅ 策划分析增强（A/B对比模式）
6. ✅ 前端API URL改为相对路径
7. ✅ FastAPI 服务所有前端页面

### P1（Demo增强）— 第8-14天
8. 事实核查 API + UI
9. 逻辑谬误识别 API + UI
10. 信源交叉验证 API + UI
11. 立场光谱可视化
12. 企业版关键词管理 + mock监测
13. 自动回应生成（5种模板）
14. 传播追踪网络图
15. 站内通知系统
16. 免费增值功能门控

### P2（文档描述/占位）— 第15天+
17. 深度伪造检测（UI占位 + 技术文档说明）
18. DOC/PDF报告导出
19. 竞品监测基础模块
20. 地域热力图
21. MIROFISH效果模拟（仅文档）
22. 审计日志基础记录
23. 数据导出/删除
24. 个人升级企业流程

---

## 五、竞争差异化

| 维度 | 现有竞品(识微/清博/舆情通/梅花网) | 知舆独特优势 |
|------|------|------|
| 产品定位 | 纯企业舆情监测 | **个人审辩思维 + 企业舆情中台** 双版本 |
| 事实核查 | 无 | **独有** |
| 逻辑谬误识别 | 无 | **独有（中国市场零竞品）** |
| 多语言交叉验证 | 无 | **独有** |
| 深度伪造检测 | 无 | **独有** |
| 视频情绪分析 | 无 | **独有** |
| 策划风险预判 | 无 | **独有（事前预防）** |
| 自动回应生成 | 手动模板 | **AI生成5种回应** |
| 观点立场光谱 | 无 | **独有** |
| 用户入口 | 企业单一入口 | **个人免费→企业付费 自下而上漏斗** |

**核心护城河**：在中国舆情赛道中，知舆是唯一将"批判性思维工具"（参考MIT的MITA）与"企业舆情中台"结合的产品。个人版创造差异化流量入口，企业版实现商业变现。

---

## 六、前后端关键文件清单

### 后端新建
- `app/dependencies.py` — 统一认证
- `app/models/enterprise.py` — 企业版模型
- `app/models/critical_thinking.py` — 审辩思维模型
- `app/api/enterprise.py` — 企业版路由
- `app/api/critical_thinking.py` — 审辩思维路由
- `app/services/fact_checker.py`
- `app/services/fallacy_detector.py`
- `app/services/cross_verifier.py`
- `app/services/auto_responder.py`
- `app/services/spread_tracer.py`
- `app/services/report_exporter.py`

### 后端修改
- `app/main.py` — 注册新路由、更新静态文件服务
- `app/models/user.py` — 增加 user_type 等字段
- `app/schemas/user.py` — UserResponse 增加 user_type
- `app/api/auth.py` — JWT含user_type、/auth/me修复、版本切换
- `app/api/history.py` — 替换user_id=1
- `app/api/monitor.py` — 替换user_id=1
- `app/api/chat.py` — 替换默认user_id
- `app/api/profile.py` — 替换默认user_id
- `app/api/settings.py` — 用get_current_user
- `app/api/notifications.py` — 用get_current_user
- `app/api/care.py` — 用get_current_user
- `app/models/__init__.py` — 导入新模型

### 前端新建
- `web/landing.html`
- `web/enterprise.html`
- `web/shared/css/theme.css`
- `web/shared/css/components.css`
- `web/shared/js/api-client.js`
- `web/shared/js/store.js`
- `web/shared/components/auth-modal.js`
- `web/shared/components/owl-chat.js`

### 前端修改（从 desktop.html 提取）
- `web/personal.html` （从 `desktop/desktop.html` 提取 + 新增审辩功能页）

### 废弃
- `predict_app.py` — Flask服务，功能已被FastAPI覆盖
- `start_predict.bat` — 不再需要
- `mobile.html` — 暂不更新

---

## 七、验证方法

1. 启动后端：`python run.py`，确认无报错
2. 注册个人账号 → 登陆 → 看到个人版界面和功能
3. 升级为企业版 → 看到企业版仪表盘
4. 企业版策划分析 → 上传文件 → 获取10维风险报告
5. 企业版关键词监测 → 添加关键词 → 看到mock数据
6. 个人版事实核查 → 输入声明 → 获取验证结果
7. 个人版逻辑谬误 → 输入文本 → 获取谬误识别
8. 版本切换 → 点击按钮 → 无刷新在个人/企业UI之间切换
9. API文档访问 `http://localhost:8000/docs` → 所有API分组正确
10. 健康检查 `http://localhost:8000/health` → `{"status":"ok"}`
