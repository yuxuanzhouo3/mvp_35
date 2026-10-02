# PickGlobal 架构

选品分析与出海获客。对外只有两条产品路径，没有第三条产品线。本文把 [project.md](project.md)、[front.md](front.md)、[back.md](back.md)、[admin.md](admin.md)、[workflow.md](workflow.md) 和当前仓库收成一张图。产品目标以 `project.md` 的 4S 为准；当前能跑起来的形状以代码为准。

使用教程录像：`demo/pickglobal-user-guide.mp4`。

```text
【A】选品与分析报告 →「一键获客」跳进 B
【B】九路获客 → 触达成交 → 冷客启动 / 流失召回
      ↑_______________ 反馈回流商品判断与线索分 _______________|
```

| 路径 | 用户看见的 | 代码边界 |
| --- | --- | --- |
| **A** | 双向入口、路线市场、分析引擎、报告、一键获客 | `front/app/workspace/products`、`front/app/workspace/reports`、`backend/app/modules/selection.py`、`backend/app/services/profit.py` |
| **B** | 九路获客、成交、冷启、召回 | `front/app/workspace/acquire`、`backend/app/modules/acquisition.py`、`backend/app/modules/providers.py` |

硬规则：金额、评分、是否流失只由规则引擎计算，模型不能改数。触达顺序是生成草稿、人工批准、再发送。查询带 `tenant_id`。长任务返回 `202`，由 worker 完成。

---

## 1. 现在跑的是什么

发布线见 [workflow.md](workflow.md)：日常在 `yzcmf`，合并到 `test`，再合并到 `pro`。版本号是两段数字。2026-10-01 时 `test` 为 `1.3`，`pro` 仍为 `1.2`。

| 层 | 现在 | 目标 |
| --- | --- | --- |
| 客户端 | `front/` Next.js 16.3.3 + TypeScript + Tailwind + shadcn/ui。开发端口 3000，`/api` 反代到 API | Web / 手机 / iPad / 微信小程序 / Mac / Win / Linux；iOS 与 Android 提供原生能力 |
| API | `backend/` Python 3.12 + FastAPI + Pydantic 2，端口 8000 | 腾讯云 CloudBase 云托管，同地域 |
| Worker | `python -m app.workers.loop`，与 API 同镜像不同命令 | 分析、导入、发现、发信、召回出队；S2 接 TDMQ |
| 存储 | 默认 `STORAGE_ENGINE=json`，文件 `backend/data/store.json`。`cloudbase` 把同一批文档写入 CloudBase PostgreSQL 的 `documents` 表，不双写 | 主库 PostgreSQL。Redis、MQ、对象存储为辅 |
| 关系型形状 | `backend/db/sql/0001_core` 与 `backend/db/sql/0001_postgres_shape` 各有 `up.sql` / `down.sql` | 用户、支付、商品、报告、线索、活动、召回、KPI、审计都进表，并开 RLS |
| 登录 | 工作台请求带 `Authorization: Bearer demo`。邮箱和手机注册登录可发 access / refresh。CloudBase Auth 仍是 503 | JWT / OAuth2、RBAC、会话、审计 |
| AI / 邮件 / 支付 | 混元默认关，解释走规则文案。SES 为 mock。微信支付未接通 | 混元只从后端调用；SES 只从 worker 调用；入账只认验签 |

进程边界：`web`、`api`、`worker` 分开。浏览器和 Next.js 客户端不持有数据库凭证。

```text
浏览器
  → Next.js 16（/ 、/workspace 、/admin）
  → rewrite /api/* → FastAPI /api/v1
  → DocumentStore（JSON 或 CloudBase documents）
  → jobs 集合
  → worker 执行后写回同一存储
```

---

## 2. 4S

| S | 问题 | PickGlobal 的答案 |
| --- | --- | --- |
| Scenario | 做什么 | 登录与订阅之后：自有导入或帮我选品 → 四维报告 → 一键获客 → 九路线索、成交、召回 → 八率 + 五时效 |
| Service | 谁来做 | MVP / SVP 是 FastAPI 模块化单体。Business 再按业务域拆部署，不按技术层拆 |
| Storage | 怎么存 | 目标是 PostgreSQL + `tenant_id` + RLS。现在是文档集合，表结构已备好 up/down |
| Scale | 变大怎么办 | 先加 worker、缓存、只读副本和索引。查询变慢超过 2 倍时先调索引和分区，不先拆微服务 |

### 2.1 Scenario

面向跨境卖家。工作台只有三块：选品分析、获客经营、看板。

| 场景 | 系统必须做的 | 成功信号 |
| --- | --- | --- |
| A1 双向入口 | 表单、CSV、国内货源目录写入同一个 `products` | 三条入口都能入库 |
| A2 路线市场 | 冻结货源地、目标市场、路线、税务口径、币种 | 改市场后必须重算才出新报告 |
| A3 分析引擎 | 规则算利润、税务、时效、风险；模型只写解释 | 关掉模型仍有 metrics；分析时效 P50 ≤ 2 分钟 |
| A4 报告 | 四维报告 + 一键获客，携带 `seed_analysis_id` | 行动率 ≥ 50% |
| B1–B5 主获客 | provider 归一化进统一 `leads` | 线索合格率 ≥ 60%；线索时效 ≤ 3 分钟 |
| B 触达 | 未批准不能发 | 触达率 ≥ 95%；退信 < 1.5%；投诉 < 0.1% |
| B 成交 | 送达后 14 天内回复或赢单计为有效获客 W | 获客率 ≥ 8%；获客时效 ≤ 3 天 |
| B 冷启 / 召回 | 规则入队，模型只写文案 | 冷客激活率 ≥ 25%；召回成功率 ≥ 10%；时效 P50 ≤ 24 小时 |
| B6–B9 | 挂在同一漏斗；RaaS 账本单列 | 不污染普通获客率 |
| 支付 | 验签后入账，整数分 + 幂等键 | 失败可切回旧支付版本 |

默认市场：货源中国、目标美国、中美税、成本人民币、售价美元。可扩到香港、澳大利亚和一部分内陆。

非功能：同步 API 的 MVP P95 ≤ 500 ms。可用性 MVP 99.5%、SVP 99.9%、Business 99.95%。并发台阶：MVP < 1 千、SVP < 1 万、Business < 10 万，之后 100 万、1000 万、1 亿。合规包括 GDPR、CCPA、PIPL、退订和退信 / 投诉红线。

利润：

```text
R = target_price_usd
C = 采购折 USD + 包装 + 国内段 + 国际段
F = R × (platform_fee_rate + payment_fee_rate)
T = 关税等
N = R − C − F − T
利润率 = N / R
```

落库字段：`net_margin`、`net_profit_usd`、`fx_usd_cny`、`rules_version`（当前 `pg-rules-1.0`）。

受众口径：A = 批准受众减去抑制、退信和无邮箱；D = A 里至少一封送达；W = 触达后 14 天内回复或赢单。分母为 0 时界面显示「—」。对外比较用租户中位数，窗口默认 30 天。

### 2.2 Service

```text
Client
  Web · iOS · Android · iPad · 微信小程序 · Mac · Win · Linux
        │
API Gateway
  Auth · Rate limit · Routing · WAF · Audit
        │
BFF（同一核心，按端裁剪字段；Business 再拆部署）
  Web · Mobile · iPad · Mini program · Desktop
        │
Core（现在是 app/modules 与 app/services，不是九个微服务）
  User · Payment
  Product · Selection · Report
  Acquisition · Lead · Campaign · Recall
  AI · GEO/SEO · Content · Digital human
  Channel · RAAS · Analytics
        │
Infrastructure（腾讯云）
  PostgreSQL · Redis · MQ · Object storage
  Search · pgvector · CDN · Scheduler · Observability
```

`back.md` 把同一套核心收成三个圈，外加一个 Copilot：

1. 商品智能：导入、利润 / 税务 / 物流、报告。
2. 客户发现：搜索、归一化、去重、质量分。
3. 触达与召回：草稿、批准、发送、事件回流、冷启与召回。

圈 3 的打开、回复、退信和成交会回到圈 2 的线索分，也会回到圈 1 的商品判断。反馈带来源、时间和关联 ID。

同步接口只做登录态、CRUD、查询和创建任务。这些必须异步：CSV 导入、分析、报告生成、客户发现、批量发信、SES 回调、流失扫描、PDF 导出。

路径 A：

```text
POST /products | /products/imports | /catalog/adopt
  → 冻结 origin / target / tax
  → POST /products/{id}/analyses   202
  → worker 写 metrics，再写解释
  → GET /analyses/{id}
  → POST /analyses/{id}/acquire    带上 seed_analysis_id
```

路径 B：

```text
LeadProvider.search
  → normalize / dedupe / score
  → leads
  → campaign 草稿 → approve → send job
  → webhook / 信号
  → 成交标记
  → 日扫 → activation / recall
```

```python
class LeadProvider(Protocol):
    channel: str  # ecommerce|social|expo|agency|enrichment|geo_seo|content_dh|cross_border|raas
    async def search(self, query: LeadSearchQuery) -> LeadSearchResult: ...
```

新平台 = 新 provider + `source_channel`，不新建线索主表。

事件信封向后兼容，带 `version`。名字包括：`user.registered`、`user.login`、`payment.succeeded`、`product.imported`、`selection.completed`、`report.generated`、`acquisition.started`、`lead.discovered`、`lead.qualified`、`campaign.delivered`、`campaign.opened`、`campaign.replied`、`deal.won`、`recall.triggered`、`kpi.updated`、`ai.called`、`digital_human.generated`、`raas.settled`。

状态机：

```text
User:     pending → active → suspended → deleted
Payment:  created → pending → succeeded → failed → refunded
Report:   draft → analyzing → completed → acquired
Task:     created → running → paused → completed → failed
Lead:     new → scored → qualified → contacted → replied → won → lost → recalled
Campaign: draft → scheduled → sending → sent → paused → completed
Recall:   triggered → queued → delivered → recovered → failed
```

### 2.3 Storage

目标主库是 PostgreSQL。PDF、导入文件、数字人素材进对象存储，库里只留 key、hash、MIME。原则：`tenant_id` 加 RLS；MVP 单实例，SVP 起主从，看板走只读副本；大表按 `created_at` 月分区；高频字段 B-Tree，JSONB 用 GIN；Redis 放会话、验证码、限流、热点报告和任务锁；审计 append-only；列表用游标。每个 migration 同时有 `up` 和 `down`。

核心表（见 `project.md` §5，落地脚本在 `backend/db/sql/0001_core/up.sql`）：

```text
tenants · users · roles · permissions · sessions · audit_logs
payments · subscriptions · invoices · refunds
products · selection_reports
acquisition_tasks · leads · campaigns · deliveries · deals · recalls
kpi_metrics · ai_calls
```

预留列可空、不删：`shard_key`、`region`、`compliance_region`、`feature_flags`、`ai_model_version`、`raas_rule`、`agency_id`、`channel_id`、`recall_trigger`、`kpi_period`。

现在的文档集合和目标表：

| 现在写入的集合 | 目标表 |
| --- | --- |
| `products` / `product_sources` | `products` |
| `analysis_reports` / `selection_reports` | `selection_reports` |
| `leads` | `leads` |
| `campaigns` / `outreach_messages` | `campaigns` / `deliveries` |
| `activation_jobs` / `recall_jobs` | `recalls`（`trigger` 区分冷启和召回） |
| `jobs` | 任务表 + 队列 |
| `payment_orders` / `usage_ledger` | `payments` / `subscriptions` + 幂等账本 |
| `metric_snapshots` | `kpi_metrics` |

最小写入顺序：`product` → 报告 → `leads` → `campaigns` → `deliveries` → `deals` → `recalls` → `kpi_metrics`。

`CloudBaseStore` 与 `DocumentStore` 使用同一套集合 API。切到 `STORAGE_ENGINE=cloudbase` 时需要 `CLOUDBASE_ENV_ID`。测试强制 JSON，避免打到远程库。

### 2.4 Scale

| 阶段 | 用户量 | 架构 | 交付焦点 |
| --- | --- | --- | --- |
| MVP | < 1 千 | 单体 + PostgreSQL 单实例 + Redis | 登录、支付骨架、导入、mock 目录、报告、邮件触达、看板 |
| SVP | < 1 万 | 模块化单体 + MQ + 只读副本 | 多租户、RBAC、订阅、PDF、评分、召回、AI 文案 |
| Business | < 10 万 | 按域拆分 + 读写分离 + 分区 | 九路正式对接 |
| Speed up 1–3 | 100 万 → 1 亿 | 缓存、CDN、分片、单元化、多活 | 多币种、Agent、全球合规。多活默认关 |

扩容信号：官网慢就上 CDN；分析或发现变慢就加 worker，先出 metrics 再等模型；发信排队或投诉抬头就分 topic、限速、独立 IP；看板打主库就改走只读副本和 `kpi_metrics` 快照。错误率 > 1% 或 P95 > 2 倍时按第 8 节回退，不在故障版本上加机器。

---

## 3. 客户端

一套 4S，多端渲染。核心链路在各端得到同一业务结果。小屏走步骤，大屏走工作台。端上只缓存，主数据在服务端。

| 端 | 交互 | 现在 |
| --- | --- | --- |
| Web | 多栏、表格、图表 | `/` 官网，`/workspace` 工作台，`/admin` 平台后台 |
| 手机 | 单列、底部导航 | 工作台底栏：看板、选品分析、获客经营 |
| iPad | 分栏、拖拽、手写 | 客户端识别为 iPad；分栏 BFF 未单独发版 |
| 微信小程序 | 微信登录、分享、订阅消息 | 识别占位；`auth.miniprogram` 关闭 |
| Mac / Win / Linux | 多窗口、快捷键 | 同一 Web 工作台，按 UA 标注系统 |
| 手表 | 可捏合缩放页面 | 没有独立手表应用 |

检测在 `front/lib/client-adapter.ts`。计划中的首屏聚合（写入仍走核心接口）：

```http
GET /api/v1/mobile/home
GET /api/v1/ipad/workbench
GET /api/v1/miniprogram/home
GET /api/v1/web/dashboard
GET /api/v1/desktop/workbench
```

页面：

| 路由 | 作用 |
| --- | --- |
| `/` | 两条路径、九路说明、样例报告、FAQ |
| `/workspace` | 八率 + 五时效，读 `GET /api/v1/metrics` |
| `/workspace/products` | 手动、CSV、货源目录，然后「开始分析」 |
| `/workspace/reports/[id]` | 市场、利润、税务、物流、风险；「一键获客」 |
| `/workspace/acquire` | 发现、线索池、草稿 / 批准 / 发送、冷启、召回、分成账本 |
| `/admin` | 平台运营。总览读同一套租户指标 |
| `/admin/ads` `/users` `/analytics` `/invitations` `/recall` | 广告、用户、行为、邀请、平台召回的界面。这些页当前是静态演示数据 |

工作台请求在 `front/lib/api.ts`：`Authorization: Bearer demo`，路径前缀 `/api/v1`。

---

## 4. 后端模块

一个 FastAPI 应用，`backend/app/main.py` 挂两套路由：业务路由 `create_router()` 和契约占位 `create_contract_router()`。逻辑组件不是首版微服务。

| 组件 | 代码 | 职责 |
| --- | --- | --- |
| Identity | `app/services/identity.py`、`app/modules/auth.py` | 注册、登录、租户、`Bearer demo`、会话 |
| Billing | `app/modules/payment.py`、`app/api/v1/pay_routes.py` | 套餐、订单、额度、代理分成、RaaS 抽成、验签 |
| Selection | `app/modules/selection.py`、`app/services/profit.py` | 商品、分析任务、报告、一键获客 |
| Acquisition | `app/modules/acquisition.py`、`app/modules/providers.py` | 九路发现、线索、活动、冷启、召回 |
| Jobs | `app/modules/jobs.py`、`app/workers/execute.py`、`app/workers/loop.py` | 入队、执行、进度、幂等 |
| Metrics | `app/services/metrics.py`、`app/modules/kpi_view.py` | 八率、五时效、红线 |
| AI | `app/modules/ai_gateway.py`、`app/api/v1/ai_routes.py` | Copilot 与模型调用；默认关闭时规则仍出数 |
| Admin API | `app/api/v1/admin_routes.py` | 平台用户、广告、邀请、分析、平台召回、审计 |
| Store | `db/store.py`、`db/cloudbase_store.py` | 文档仓储 |
| Flags | `backend/config/flags.json` | 未开通能力默认关 |

已接通的主要接口（前缀 `/api/v1`）：

```http
GET  /health/live
GET  /health/ready
POST /auth/bootstrap
POST /auth/logout
GET  /me
GET  /tenants/current

POST /products
GET  /products
POST /products/imports                 202
POST /products/{id}/analyses           202
GET  /analyses/{id}
POST /analyses/{id}/acquire
GET  /catalog/search
POST /catalog/adopt

POST /lead-searches                    202
GET  /leads
POST /leads/{id}/signals
POST /campaigns
POST /campaigns/{id}/drafts
POST /campaigns/{id}/approve
POST /campaigns/{id}/send              202
POST /lifecycle/scan                   202
GET  /activation/jobs
GET  /recall/jobs

GET  /metrics
GET  /jobs/{id}
POST /billing/orders
POST /billing/agency/commissions
POST /billing/raas/commissions
```

占位接口返回未开通，不写生产账本，不发真实触达：`POST /auth/sso`、`POST /payments/raas`、`POST /selection/auto-deal`、`POST /acquisition/social|ecommerce|expo|agency`、`POST /ai/agent`、`POST /ai/finetune`、`POST /digital-human/generate`、`POST /geo/seo`、`POST /raas/settle`。

九路渠道（UI 与 `source_channel`）：

| 代号 | 通道 | 分层 | 演示行为 |
| --- | --- | --- | --- |
| B1 | 电商 Amazon、Temu、Walmart、淘宝、拼多多 | 主获客 | mock 线索进同一池 |
| B2 | 社交 LinkedIn、Facebook、微信、抖音、小红书、快手 | 主获客 | 同上；正式开通前 Flag 关 |
| B3 | 线上展会 | 主获客 | 会期发现，会后进冷启 / 召回 |
| B4 | 12 代理 | 主获客 | 线索与分成账本分开 |
| B5 | 企查查、天眼查等 | 主获客 | 去重、打分、留痕 |
| B6 | GEO / SEO | 优化，也可卖本品 | 落地页归因，不另开线索表 |
| B7 | 内容工厂、数智人、线下客流 | 优化 | 数智人是 DEMO 占位，不买 10 小时包 |
| B8 | 跨境元素 | 优化 | 约 80% 中美 / 中港 / 中澳，20% 内陆 |
| B9 | RaaS | 销售 PickGlobal 本身 | 抽成不计入普通获客率 |

质量分阈值默认 60（`quality_threshold`）。B4 / B9 金额是整数分。服务端先验签，同一 `idempotency_key` 不重复入账。演示环境可以用 `POST /dev/ledger-signature` 取签名；浏览器没有签名密钥。

---

## 5. 平台后台

`/admin` 是平台运营，不是企业租户里的 `owner/admin`。企业管理员只看本租户。平台召回是 PickGlobal 注册用户的回流；工作台里的 `recall_jobs` 是企业对海外线索的业务召回。两套数据、接口和权限分开。

增长闭环：广告曝光 → 访问注册 → 分群与流失 → 邀请或召回 → 回流付费 → 归因。

```text
/admin
├── overview        八率 + 五时效（已接 GET /metrics）
├── ads             广告位、素材、投放
├── users           用户画像、隐私、风险
├── analytics       事件、漏斗、留存、路径
├── invitations     邀请码、奖励、反作弊
├── recall          平台用户召回（不是海外线索召回）
├── jobs            批处理
├── audit           审计
└── settings        权限与字典
```

规则决定对象，模型只写解释或文案。批量动作先预览命中人数。封禁、导出、发信要更高权限和原因。列表默认脱敏。

后台 API 已在 `admin_routes.py`（`/admin/users`、`/admin/ads`、`/admin/invitations`、`/admin/analytics`、`/admin/recall`、`/admin/audit`）。对应前端子页仍用静态样例，总览已经读真实指标。

---

## 6. 开关、降级、回退

`backend/config/flags.json` 默认全部关闭：SSO、MFA、OAuth、小程序登录、租户切换、RaaS 支付、自动成交、社交 / 电商 / 展会 / 代理的正式通道、AI Agent、微调、数字人、GEO/SEO、RaaS、全球多活。

降级：AI 失败改走规则引擎；邮件失败可改站内信。解释和规则金额偏差超过 5 个百分点时切回规则。

回退是架构能力，脚本在 [rollback/](rollback/)。基线是 CloudBase 文档方案。

```bash
./rollback/rollback.sh pin-tag --repo .
./rollback/rollback.sh migrate-up --store backend/data/store.json --journal rollback/state/wal.jsonl
./rollback/rollback.sh run --store backend/data/store.json --home rollback/state --journal rollback/state/wal.jsonl --events rollback/state/events.jsonl
```

`run` 的顺序：关 Flag、流量切回 `baseline-cloudbase`、migration down、失败则 PITR、事件按幂等键重放且第二次不得改账本、AI 偏差过大则改回规则。代码回退默认只打印计划；`--apply` 才检出基线路径，不 reset，也不动 `rollback/` 和 `project.md`。

| 变更 | 回退 | 触发 |
| --- | --- | --- |
| 需求 | Git revert 或检出 Tag | KPI 不可复算、合规风险 |
| 服务 | Flag、停金丝雀、rollout undo | 错误率 > 1%，P95 > 2 倍 |
| 数据库 | `down.sql`，不行则快照 / PITR | 数据异常、锁表超过 5 秒、KPI 断档 |
| 容量 | 切回上一版 `config/s4-*` | CPU 或内存高且扩容无效、成本超预算 |
| 支付 | 停新单并切回旧通道 | 失败率 > 0.5% |
| 触达 | 限流并停新发送 | 送达率 < 95%，退信 > 1.5%，投诉 > 0.1% |

Tag 形式 `s{1-4}-v{major}.{minor}.{patch}`。发布版本本身保持 `x.y`。

---

## 7. 仓库地图

```text
mvp_35/
├── architecture.md          本文
├── project.md               产品 4S、KPI、表、时间线、回退策略
├── front.md                 多端呈现与 BFF
├── back.md                  腾讯云 / CloudBase 后端方案
├── admin.md                 平台运营后台
├── workflow.md              yzcmf → test → pro
├── front/                   Next.js 工作台、官网、/admin
├── backend/
│   ├── app/                 FastAPI、模块、worker
│   ├── config/              settings、flags、s3 配置
│   ├── db/sql/              PostgreSQL up/down
│   ├── db/cloudbase/        documents 迁移
│   └── data/store.json      本地文档库（不作为契约）
├── rollback/                可执行回退
├── test/                    mvp、svp、business
└── demo/                    用户教程录像
```

本地：

```bash
# API
cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# Worker
cd backend && .venv/bin/python -m app.workers.loop
# Web
cd front && pnpm dev --port 3000
```

打开 `http://localhost:3000`。工作台用演示令牌，不需要先注册。
