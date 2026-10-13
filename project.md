# PickGlobal · Oversea Market Selling

选品分析与出海获客全链路闭环。对外只有两条产品路径：跨境选品或自有商品 → 分析报告；跨境获客 → 数字人邮件、成交、流失召回。冷客启动 / 流失召回是路径 B 的生命周期阶段。

本文权威顺序：

1. **功能拆解**（产品要什么）
2. **量化 KPI**（八率 + 五时效）
3. **系统设计 4S**（Scenario / Service / Storage / Scale）
4. **功能模块**（登录 / 支付 / 核心功能 / AI 模型）
5. **存储**（PostgreSQL）
6. **扩展性**（DEMO 交付时间线）
7. **功能占位与留白**
8. **4S 回退**（代码 + DB 可立刻回到上一状态）

对齐 [front.md](front.md) / [back.md](back.md) / [admin.md](admin.md)。本文是目标 4S。当前仓库基线仍是 `back.md` 的 CloudBase 云文档方案；落地本文件前，回退目标就是那一版代码与数据。

## 硬约束

| 项 | 锁定 |
| --- | --- |
| 产品 | 路径 A 选品报告 + 路径 B 九路获客；不新开第三条产品线 |
| 客户端 | Web / 手机 / iPad / 微信小程序 / Mac / Win；iOS 与 Android 提供原生能力。交互与回退见 [front.md](front.md) |
| 服务端 | **腾讯云**：Code + DB + IP |
| 全栈 | Next.js 16 + TypeScript + Tailwind + shadcn/ui · Python FastAPI |
| AI | 腾讯混元走 AI Model Service；Prompt / 模型版本可切回；数字人 DEMO 占位，不买 10h 包 |
| 主库 | **PostgreSQL**（MVP 单实例）。Redis、MQ、对象存储为辅 |
| 选品主数据 | 自有导入 / 帮我选品。Amazon 等优先作路径 B 线索源 |
| 获客 | 九路 provider；DEMO 可 mock；海外正式开通前过合规 |
| 金额 | 规则引擎 + `Decimal` / 整数分；模型不能改数 |
| 触达 | AI 生成 → 人工批准 → 发送 |

```text
【A】选品与分析报告 →「一键获客」跳进 B
【B】九路获客 → 触达成交 → 冷客启动 / 流失召回
      ↑_______________ 反馈回流商品判断与线索分 _______________|
```

| 产品 | 用户可见 | 代码边界 |
| --- | --- | --- |
| **A** | 双向入口 · 路线市场 · 分析引擎 · 报告 + 一键获客 | `app/products` · `app/analysis` |
| **B** | 九路获客经营（含成交 / 召回） | `app/leads` · `app/campaigns` · `providers/*` · `app/activation` · `app/recall` |

---

## 1. 功能拆解

### 一、选品与分析报告

```text
双向入口 → 路线与市场设定 → 选品分析引擎 → 选品报告
                                              ↓
                                    【一键获客】跳转获客板块（路径 B）
```

| # | 功能 | 路径 | 特色 |
| --- | --- | --- | --- |
| **A1** | **双向选择入口** | **自有导入**（表单 / CSV）或 **帮我选品**（国内货源目录） | 两条入口汇入同一 `products` |
| **A2** | **路线和市场设定** | 货源地 / 目标市场 / 物流路线 / 税务口径 / 售价币种 | MVP 默认货源 CN、目标 US、中美税、成本 CNY / 售价 USD；可扩展中港 / 中澳 |
| **A3** | **选品分析引擎** | 异步 job：规则算利润 · 税务 · 时效 · 风险；模型只做解释 | 金额可审计；`rules_version` 快照 |
| **A4** | **输出选品报告** | 四维报告 + **一键获客**，携带 `seed_analysis_id` | 报告不是终点；抬行动率 ActR |

### 二、获客

统一漏斗：`线索获客 → 触达 → 成交标记 → 冷客启动或流失召回`。

```text
1–5 = 主获客
6–8 = 优化（供 1–5 用；销售本品也能用）
6–9 = 可用来销售 PickGlobal 本身
```

| # | 路径 | 闭环 | 分层 | 特色 |
| --- | --- | --- | --- | --- |
| **B1** | **电商** Amazon · Temu · Walmart · 淘宝 · 拼多多 | 线索 + 成交 + 召回 | 主获客 | 询盘 / 订单买家 / 沉默买家统一进 `leads` |
| **B2** | **社交** LinkedIn · Facebook · 微信小程序 · 抖音 · 小红书 · 快手 | 线索 + 成交 + 召回 | 主获客 | 公域互动沉淀；小程序可同栈登录 |
| **B3** | **线上展会** | 线索 + 成交 + 召回 | 主获客 | 会期削峰；会后进冷启 / 召回 |
| **B4** | **12 代理渠道** | 批量获客 + 成交 + **分成** | 主获客 | 渠道子账户；账本与分成分离 |
| **B5** | **智慧大脑** 企查查 + 天眼查 + etc | 线索集合 + 成交 + 召回 | 主获客 | 去重、质量分、合规留痕 |
| **B6** | **GEO / SEO** | 线索 + 成交 + 召回 | 优化；可自销 | 供 1–5；落地页归因 |
| **B7** | **AI 内容工厂 + 数字人 + 线下客流** | 线索 + 成交 + 召回 | 优化；可自销 | 供 1–5；数智人占位 |
| **B8** | **跨境元素复现** | 线索 + 成交 + 召回 | 优化；可自销 | 约 **80%** 中美 / 中港 / 中澳 + **20%** 内陆 |
| **B9** | **RAAS** | 官网成功抽成 + APP 账户销售（类比 elink） | 本品销售 | 卖结果抽成；ledger 与套餐可并存 |

硬规则：统一 `leads` + `source_channel`；冷启 / 召回规则入队，模型只写文案；B4 / B9 整数分、幂等账本、验签后才发佣或记抽成。

---

## 2. 量化 KPI

金额只用规则引擎。默认滚动 **30 天**。分母为 0 → `—`。对外用租户**中位数**。

### 八率

| # | 指标 | 代号 | 主要服务功能 | 公式 | S2 目标 | 角色 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 利润率 | `N%` | A3 / A4 | `N/R`；看板 `median(net_margin)` | 可复算；推荐 ≥15%；偏差 ≤5pt | 四率 |
| 2 | 行动率 | `ActR` | A4→B | 点「一键获客」或采纳的报告 ÷ 完成报告 | ≥50% | 四率 |
| 3 | 触达率 | `TR` | B 触达 | delivered 人数 D ÷ 计划受众 A | ≥95% | 四率 |
| 4 | 打开率 | `OR` | B 触达 | unique 打开 ÷ D | ≥40%（辅助） | 四率 |
| 5 | **获客率** | `AR` | B 成交 | 有效获客 W ÷ 触达 S（≈D） | **≥8%（北星）** | 效果 |
| 6 | 线索合格率 | `QR` | B1–B5 发现 | `score≥θ` ÷ 入库 | ≥60% | 质量 |
| 7 | 冷客激活率 | `ActR_cold` | B 冷启 | 序列内 open∨reply ÷ 入队 | ≥25% | 生命周期 |
| 8 | 召回成功率 | `RecR` | B 召回 | 回暖 ÷ 召回触达 | ≥10% | 生命周期 |

红线：送达率（按封）≥95%；bounce &lt;1.5%；complaint &lt;0.1%。

### 五时效（P50；超时记失败）

| # | 指标 | 代号 | 主要服务功能 | 公式 | S2 |
| --- | --- | --- | --- | --- | --- |
| 1 | 分析时效 | `AnaT` | A3 | 完成 − 请求 | ≤2 min |
| 2 | 线索时效 | `LeadT` | B 发现 | discovery 成功 − 发起 | ≤3 min |
| 3 | 获客时效 | `AcqT` | B 成交 | first_W − first_delivered（仅 W） | ≤3 天 |
| 4 | 激活时效 | `ActT` | B 冷启 | 首封 delivered − 入队 | ≤24 h |
| 5 | 召回时效 | `RecT` | B 召回 | 首封 delivered − 触发 | ≤24 h |

```text
A = approve 受众 − suppressed / bounced / 无邮箱
D = A 中至少 1 封 delivered
W = 触达后 14 天内 replied 或赢单 / 约见
```

看板：**首屏四率 + 北星 AR**；时效条可折叠；红线限流；ActT / RecT 的 P95 &gt;72h 告警。

### 利润公式

```text
R = target_price_usd
C = 采购折USD + 包装 + 国内段 + 国际段
F = R × (platform_fee_rate + payment_fee_rate)
T = 关税等
N = R − C − F − T     → 利润率 N/R
```

落库：`net_margin`、`net_profit_usd`、`fx_usd_cny`、`rules_version`。

| 功能 | 必看 KPI | 过线信号（S2） |
| --- | --- | --- |
| A1 | 导入成功率；目录搜索可用性 | 手动 + CSV + mock 目录均可入库 |
| A2 | 报告含正确 market / route 快照 | 改市场后必须重算才出新报告 |
| A3 | `N%` · `AnaT` | 关模型仍有 metrics；P50 ≤2 min |
| A4 | `ActR` | ≥50%；携带 `seed_analysis_id` |
| B1–B5 | `QR` · `LeadT` · `AR` | QR ≥60%；LeadT ≤3 min；AR ≥8% |
| B 触达 | `TR` · `OR` · 送达红线 | TR ≥95%；bounce / complaint 红线 |
| B 冷启 / 召回 | `ActR_cold` · `RecR` · `ActT` · `RecT` | 率达标；P50 ≤24 h |
| B4 / B9 | 账本对账成功率 | 仅验签后入账；幂等不双发 |

---

## 3. 系统设计 4S

| S | 含义 | 核心问题 | 典型内容 |
| --- | --- | --- | --- |
| **1. Scenario** | 场景 / 需求 | 系统要做什么？ | FR / NFR、QPS、DAU、Latency、Availability |
| **2. Service** | 服务 / 架构 | 由哪些服务组成？ | Client、API Gateway、Service、Cache、DB、MQ、Object Storage |
| **3. Storage** | 数据 / 存储 | 数据怎么存、怎么访问？ | Schema、SQL、Index、Partition、Replication、Cache |
| **4. Scale** | 扩展 / 优化 | 流量变大？功能变多？ | LB、Sharding、Caching、CDN、Async、Replication、Failover |

### 3.1 Scenario

**定位。** 面向跨境卖家：登录 / 注册 / 支付订阅 → 自有导入或帮我选品 → 报告（利润、税务、时间、风险）→ 一键获客 → 九路线索、成交、召回 → 看板八率 + 五时效。支付按订阅 / 抽成 / RAAS 结算。

**功能需求**

| 路径 | 用户场景 | 系统必须完成 | 成功信号 |
| --- | --- | --- | --- |
| 登录 | 多端进入工作台 | 租户隔离、RBAC、会话 | 审计可追溯 |
| 支付 | 订阅 / 按次 / RAAS | 验签后入账 | 幂等；失败可回退旧支付版本 |
| **A1–A4** | 导入或选品 → 报告 → 一键获客 | 规则算 N / 税 / 时效 / 风险；模型只解释 | `AnaT` ≤2 min；`ActR` |
| **B1–B5** | 电商 / 社交 / 展会 / 代理 / 大数据找人 | provider 归一化进统一 `leads` | `QR` ≥60%；`LeadT` ≤3 min |
| **B 触达** | 批准后发送 | 禁未审群发 | `TR` ≥95%；送达红线 |
| **B 成交** | 回复 / 赢单 | `W` 定义固定 | `AR` ≥8%；`AcqT` ≤3 天 |
| **B 冷启 / 召回** | 未互动或沉默 | 规则入队 | P50 ≤24 h |
| **B6–B9** | 优化或卖本品 | 挂在同一漏斗；RAAS 单列 | 不污染普通 AR |

**非功能需求**

| 项 | 目标 |
| --- | --- |
| 延迟 | 同步 API：MVP P95 ≤500 ms；长任务见五时效 |
| 可用性 | MVP 99.5%；SVP 99.9%；Business 99.95% |
| 并发 | MVP &lt;1k；SVP &lt;1w；Business &lt;10w；Speed up 1 &lt;100w；Speed up 2 &lt;1000w；Speed up 3 &lt;1E |
| 安全 | JWT / OAuth2、RBAC、租户隔离、支付签名、Webhook 验签、审计日志 |
| 合规 | GDPR、CCPA、PIPL、跨境传输、邮件退订、bounce / complaint 红线 |
| 可回退 | 代码、Schema、配置、流量、事件、模型均可回到上一版 |

工作台：

```text
工作台
├── 登录 / 租户 / 支付
├── 选品分析（A1–A4）自有导入 | 帮我选品 | 路线市场 | 报告 → 一键获客
├── 获客经营（B）B1–B9 | 线索 / 触达 | 成交分成 / RAAS | 冷启动 / 召回
└── 看板  首屏四率 + 北星 AR；时效可折叠
```

共性：长任务 `202 + jobs`；金额 / 评分 / 是否流失只由规则引擎算；查询强制 `tenant_id`；provider 可 mock。

**S1 输出物：** PRD、用户故事、业务流程图、状态机、KPI 定义、API 契约、事件契约、数据字典、风控规则、合规清单。均 Git 版本化，Tag `s1-v{major}.{minor}.{patch}`。

### 3.2 Service

MVP / SVP 是 **FastAPI 模块化单体**（同镜像不同命令跑 API 与 Worker）。下表是业务域边界。Business 阶段按域拆部署，不按技术层拆。

```text
Client
  ├── Web
  ├── iOS
  ├── Android
  ├── iPad
  ├── 微信小程序
  ├── Mac
  └── Win

API Gateway
  ├── Auth · Rate Limit · Routing · WAF · Audit

BFF
  ├── Web BFF · Mobile BFF · iPad BFF · MiniProgram BFF · Desktop BFF

Core（MVP 为模块，Business 为可独立部署的服务）
  ├── User · Payment
  ├── Product · Selection Engine · Report
  ├── Acquisition · Lead · Campaign · Recall
  ├── AI Model · GEO/SEO · Content Factory · Digital Human
  ├── Channel · RAAS · Analytics

Infrastructure（腾讯云）
  ├── PostgreSQL · Redis · MQ · Object Storage
  ├── Search · Vector（pgvector 或独立向量库）
  ├── CDN · Cron / Scheduler · Observability
```

| 域 | 职责 | 关键接口 | MVP |
| --- | --- | --- | --- |
| User | 注册、登录、RBAC、租户、Session | `/auth/*` `/users/me` | 邮箱 / 手机 + 会话 |
| Payment | 订阅、抽成、RAAS、发票、Webhook | `/payments/*` `/subscriptions` | 一套验签入账 |
| Product | 自有导入、商品库、SKU | `/products` `/products/import` | 表单 + CSV + mock 目录 |
| Selection Engine | 路线市场、规则评分 | `/selection/analyze` | 规则算数 |
| Report | 报告、PDF、一键获客 | `/reports` `/reports/{id}/acquire` | 四维报告 + CTA |
| Acquisition | 获客任务编排 | `/acquisition/tasks` | 邮件一条通路 |
| Lead | 入库、评分、合格率 | `/leads` `/leads/score` | 统一 `leads` |
| Campaign | 邮件 / 社交 / 展会 / 代理触达 | `/campaigns` | 邮件；其余 Tab 占位 |
| Recall | 冷客激活、流失召回 | `/recall` | 规则入队 |
| AI Model | LLM、Embedding、Rerank、数字人 | `/ai/chat` `/ai/embed` `/ai/rerank` | 混元解释 + 文案 |
| GEO / SEO | 内容与站点优化 | `/geo/seo` | 占位 |
| Content Factory | AI 内容生产 | `/content/generate` | 占位 |
| Digital Human | 数字人邮件、视频、运营 | `/digital-human` | DEMO 占位 |
| Channel | 12 代理渠道 | `/channels` | 占位 + 账本科目 |
| RAAS | 成功抽成、账户销售 | `/raas` | 占位 + ledger 科目 |
| Analytics | 八率 + 五时效 | `/kpi/dashboard` | 快照可算 |

同步走 REST（服务间可 gRPC）。异步走 MQ。重任务（分析、触达、召回、内容）必须出队。AI 失败降级规则引擎；邮件失败可降级站内信。限流按租户、IP、API、通道。

**事件（向后兼容，带 `version`）：**

```text
user.registered · user.login · payment.succeeded
product.imported · selection.completed · report.generated
acquisition.started · lead.discovered · lead.qualified
campaign.delivered · campaign.opened · campaign.replied
deal.won · recall.triggered · kpi.updated
ai.called · digital_human.generated · raas.settled
```

**设计原则**

1. 按业务域拆，不按技术分层拆。
2. 核心链路可独立扩容：选品、获客、支付、AI。
3. 多租户：`tenant_id` + RLS。
4. 无状态水平扩容；Trace、Metrics、Log、Audit 齐全。
5. 语言保持 Python / TypeScript。扩的是库、队列、副本和部署单元。

路径 A：`POST /products|/imports|/catalog/search` → 冻结 origin/target/tax → `POST /selection/analyze` `202` → worker 规则 metrics → 模型摘要 → `GET /reports/{id}` → CTA `/reports/{id}/acquire`。

路径 B：`LeadProvider.search` → normalize / dedupe / score → `leads` → campaign 草稿 → approve → send jobs → webhook → 成交标记 → 日扫 → activation / recall。

```python
class LeadProvider(Protocol):
    channel: str  # ecommerce|social|expo|agency|enrichment|geo_seo|content_dh|cross_border|raas
    async def search(self, query: LeadSearchQuery) -> LeadSearchResult: ...
```

### 3.3 Storage

主库 **PostgreSQL**。用户、租户、支付、商品、报告、获客任务、线索、活动、召回、KPI、审计、AI 元数据都落在这里。报告 PDF、导入文件、数字人素材、附件进对象存储，库里只留 key + hash + MIME。

原则：

1. `tenant_id` + Row Level Security。
2. MVP 单实例；SVP 起主从，看板走只读副本。
3. 大表按 `created_at` 月分区。
4. 高频字段 B-Tree；JSONB 用 GIN。
5. Redis：Session、验证码、限流、热点报告、KPI 看板、任务锁。
6. 向量用 pgvector（或之后独立向量库）。搜索用 OpenSearch / Elasticsearch，Business 再上。
7. 审计表 append-only。
8. 业务经 repository；禁止绕过 `tenant_id`。列表用游标。

表、索引、备份见 §5。每个 migration 必须有 `up` 与 `down`。

### 3.4 Scale

两条轴：**卖家变多**，**九路 / 市场变多**。

| 阶段 | 用户量 | 架构 |
| --- | --- | --- |
| MVP | &lt;1k | 单体 + PostgreSQL 单实例 + Redis |
| SVP | &lt;1w | 模块化单体 + MQ + 只读副本 |
| Business 1–10 | &lt;10w | 按域拆分 + 读写分离 + 分区 |
| Speed up 1 | &lt;100w | 缓存 + CDN + 分片 + 异步 |
| Speed up 2 | &lt;1000w | 多集群 + 单元化 |
| Speed up 3 | &lt;1E | 全球多活 + 数据同步 |

| 信号 | 动作 |
| --- | --- |
| 官网变慢 | CDN + 前端副本（Vercel） |
| AnaT / LeadT 升高 | worker 副本；先出 metrics 再等模型 |
| 发信排队、投诉抬头 | 队列分 Topic、限速、独立 IP；触达红线触发限流 |
| 看板打主库 | 只读副本 + `kpi_metrics` 快照 |
| 查询变慢 &gt;2× | 索引 / 分区；禁止先拆微服务 |
| 错误率 &gt;1% 或 P95 &gt;2× | 按 §8 回退，不在故障版本上继续加容量 |

功能变多时：新平台 = 新 `LeadProvider` + `source_channel` 枚举；展会峰值只加 worker；代理 / RAAS 复用 ledger；GEO、内容、跨境包挂在 B 漏斗上；新市场 = A2 模板 + B8 话术包。不新建线索主表，不新开产品线。

**S4 输出物：** 容量规划、压测方案、扩容手册、故障演练、成本模型、SLA / SLO。配置本身版本化为 `s4-v*`，可一键切回。

---

## 4. 功能模块

### 4.1 登录

多端登录、租户隔离、RBAC。本版做完的能力：邮箱 / 手机注册、密码登录、验证码登录、会话、忘记密码、角色权限、审计。OAuth（Google、LinkedIn、Facebook、WeChat）、小程序登录、Apple 登录、MFA、租户切换做入口与契约，完整对接按 Flag 打开。

```http
POST /auth/register
POST /auth/login
POST /auth/logout
POST /auth/refresh
POST /auth/oauth/{provider}
POST /auth/mfa/verify
GET  /users/me
```

表：`tenants` `users` `roles` `permissions` `user_roles` `sessions` `audit_logs`。

留白：SSO / SAML、企业微信 / 钉钉、生物识别、设备指纹、风险登录。接口占位 `POST /auth/sso`。

### 4.2 支付

订阅、按次、RAAS 成功抽成、发票、退款、Webhook、对账。入账只认验签回调或主动查单。整数分 + `idempotency_key`。

```http
POST /payments/checkout
POST /payments/webhook
GET  /payments
GET  /subscriptions
POST /subscriptions/cancel
POST /refunds
GET  /invoices
```

表：`payments` `subscriptions` `invoices` `refunds` `coupons` `payment_events` `tax_records`。

留白：Stripe / PayPal / 微信支付 / 支付宝的具体通道、分账、佣金结算、多级代理分成、跨境税务。RAAS 入口先占位：`POST /payments/raas`。

### 4.3 核心功能

**选品。** A1 双向入口、A2 路线市场、A3 引擎、A4 报告与一键获客。

**获客。** B1–B9 如 §1。DEMO 只打通邮件触达；电商、社交、展会、代理、智慧大脑、GEO/SEO、内容工厂、数字人、RAAS 保留 Tab、接口、表字段和事件。

**KPI。** 八率 + 五时效，口径见 §2。首屏四率 + 北星 AR。

```http
POST /selection/analyze
GET  /reports/{id}
POST /reports/{id}/acquire
POST /acquisition/tasks
GET  /leads
POST /campaigns
POST /recall
GET  /kpi/dashboard
```

表：`products` `selection_reports` `acquisition_tasks` `leads` `campaigns` `deliveries` `deals` `recalls` `kpi_metrics`。

留白：更多平台 / 代理 / 线路、自动成交、自动召回、线下 POS、供应链金融。占位：`POST /selection/auto-deal`、`POST /acquisition/social|ecommerce|expo|agency`。

### 4.4 AI 模型

为选品解释、报告摘要、获客文案、内容、数字人、召回提供能力。金额、评分、是否流失不走模型。

| 能力 | 用途 | MVP |
| --- | --- | --- |
| LLM | 报告解释、邮件、内容、对话 | 混元；可关，规则仍出数 |
| Embedding / Rerank | 商品、线索、内容 | 契约占位 |
| 分类 / 预测 | 线索合格、风险、利润、成交、召回 | 规则先算；模型只作辅助字段 |
| 数字人 | 视频、语音、邮件 | DEMO 占位 |
| OCR / 翻译 | 导入、发票、跨境文案 | 契约占位 |
| 推荐 / 风控 | 选品、渠道、垃圾与合规 | 契约占位 |

```http
POST /ai/chat
POST /ai/embed
POST /ai/rerank
POST /ai/classify
POST /ai/predict
POST /ai/translate
POST /ai/ocr
POST /digital-human/generate
```

表：`ai_calls` `ai_models` `ai_prompts` `ai_embeddings` `ai_feedback` `ai_cache`。每次调用记录 `model`、`prompt` 版本、token、`latency_ms`。

留白：自训、微调、模型路由、成本优化、多模型 A/B、AI Agent、自动工作流。占位：`POST /ai/agent`、`POST /ai/finetune`。失败降级到规则引擎，并打 `ai.called` 失败事件。

---

## 5. 存储：PostgreSQL

选型：支付 / 订阅 / 抽成要事务；商品与报告要 JSONB；多租户要 RLS；线索与触达要按时间分区；向量可先 pgvector；备份、PITR、迁移生态完整。

| 阶段 | 部署 |
| --- | --- |
| MVP | 单实例 PostgreSQL + Redis |
| SVP | 主从 + Redis + MQ |
| Business | 读写分离 + 月分区 + 搜索 + pgvector |
| Speed up | 分片 + 多集群 |
| 全球 | 多活 + 数据同步（留白，默关） |

备份：每日全量、WAL 归档、PITR、跨区副本、恢复演练。变更前额外 `pg_dump`。安全：RLS、加密、审计、脱敏、合规删除。

### 核心表

```sql
tenants(id, name, plan, status, region, created_at)
users(id, tenant_id, email, phone, password_hash, role, status, created_at)
payments(id, tenant_id, user_id, provider, amount, currency, status, external_id, idempotency_key, created_at)
subscriptions(id, tenant_id, plan, status, period_start, period_end)
products(id, tenant_id, source, title, sku, price, cost, category, attributes jsonb)
selection_reports(id, tenant_id, product_id, route, market, profit_margin, tax, time_cost, risk, score, status, rules_version, seed_ready, created_at)
acquisition_tasks(id, tenant_id, report_id, channel, status, started_at, finished_at)
leads(id, tenant_id, task_id, source, name, email, phone, company, score, status, created_at)
campaigns(id, tenant_id, task_id, channel, subject, content, status, scheduled_at)
deliveries(id, tenant_id, campaign_id, lead_id, channel, status, delivered_at, opened_at, replied_at)
deals(id, tenant_id, lead_id, amount, currency, status, won_at)
recalls(id, tenant_id, lead_id, trigger, status, delivered_at, recovered_at)
kpi_metrics(id, tenant_id, metric_code, value, period, created_at)
ai_calls(id, tenant_id, model, prompt_version, prompt_tokens, completion_tokens, latency_ms, status, created_at)
audit_logs(id, tenant_id, user_id, action, resource, ip, created_at)
```

索引：`users(tenant_id, email)` 唯一；`leads(tenant_id, email)` 唯一；`deliveries(tenant_id, campaign_id, lead_id)`；`kpi_metrics(tenant_id, metric_code, period)`；`ai_calls(tenant_id, created_at)`；`audit_logs(tenant_id, created_at)`。JSONB GIN。大表按 `created_at` 月分区。

**预留列（本版可空，不删）：** `shard_key`、`region`、`compliance_region`、`feature_flags`、`ai_model_version`、`raas_rule`、`agency_id`、`channel_id`、`recall_trigger`、`kpi_period`。

与当前 `back.md` 集合的对照（落地时迁移，不双主写）：

| 现集合 | 目标表 |
| --- | --- |
| `products` / `product_sources` | `products` |
| `analysis_reports` | `selection_reports` |
| `leads` | `leads` |
| `campaigns` / `outreach_messages` | `campaigns` / `deliveries` |
| `activation_jobs` / `recall_jobs` | `recalls`（`trigger` 区分冷启与召回） |
| `jobs` | 任务表 + MQ；五时效仍从开始/完成时间算 |
| `payment_orders` / `usage_ledger` | `payments` / `subscriptions` + 幂等账本 |
| `metric_snapshots` | `kpi_metrics` |

最小写入序：`product` → `selection_reports` → `leads` → `campaigns` → `deliveries` → `deals` → `recalls` → `kpi_metrics`。

---

## 6. 扩展性：DEMO 交付时间线

DEMO 对外可演示；录屏走 Bilibili / YouTube。每一阶段都有 Git Tag 与可回退 migration。未实现的入口保持占位，不假装已接通。

### MVP · 1 week · &lt;1k

登录、支付骨架、自有导入、帮我选品（mock 目录）、选品报告、一键获客、邮件触达、KPI 看板、PostgreSQL、Redis。

KPI：`AnaT` ≤2 min，`LeadT` ≤3 min，`TR` ≥95%，`OR` ≥40%，`AR` ≥8%（样本内可算；分母为 0 显示 `—`）。

系统：单体 + PostgreSQL + Redis + MQ + 对象存储。留白：社交、电商、代理、数字人、RAAS。

### SVP · 2 week · &lt;1w

多租户、RBAC、支付订阅、报告 PDF、多渠道触达契约、线索评分、召回、八率 + 五时效、AI 报告、AI 邮件。

KPI：`QR` ≥60%，`ActR_cold` ≥25%，`RecR` ≥10%，`ActT` / `RecT` ≤24 h。

系统：模块化单体、主从、MQ、CDN。留白：电商、社交、展会、代理、数字人的正式对接。

### Business 1–10 · 1 month · &lt;10w

按域拆服务；接入电商、社交、线上展会、12 代理、智慧大脑、GEO/SEO、内容工厂、数字人、RAAS。

KPI：八率、五时效达标；送达 ≥95%，bounce &lt;1.5%，complaint &lt;0.1%。

系统：读写分离、分区、搜索、向量。留白：全球多活、自训模型、自动成交。

### Business Speed Up 1 · 2 month · &lt;100w

缓存、CDN、分片、异步化、AI 路由、多币种、多语言、自动召回、代理结算。

KPI：P95 达标；可用性 99.95%；成本可解释。留白：全球多活、数据湖。

### Business Speed Up 2 · 3 month · &lt;1000w

多集群、单元化、数据湖、AI Agent、自动工作流、全球 CDN / 支付 / 税务 / 合规 / 召回。

KPI：跨区域可用、低延迟。留白：自研模型、边缘计算。

### Business Speed Up 3 · 1 year · &lt;1E

全球多活、自治服务、数据湖、AI 自训、边缘、全球合规 / 结算 / 供应链 / RAAS。

KPI：全球低延迟与高可用。留白：新的基础设施代际，单独立项，不写进本版契约。

---

## 7. 功能占位与留白

当前版本预留入口、接口、字段、事件、状态机和开关，不做完整实现，避免以后改契约。

| 原则 | 做法 |
| --- | --- |
| 入口 | UI 有按钮；未开通的置灰并标明占位 |
| 数据 | 表字段、事件、状态机先有 |
| 服务 | 接口返回明确的未开通响应，可 Mock |
| 开关 | Feature Flag 默认关 |
| 降级 | AI → 规则；邮件 → 站内信 |
| 合规 | 退订、审计、删除先有 |
| 成本 | AI 缓存、限流先有 |
| 扩展 | `tenant_id`、`shard_key`、`region` 先有 |

| 模块 | 留白 |
| --- | --- |
| 登录 | SSO、SAML、生物识别、设备指纹 |
| 支付 | 分账、佣金、跨境税务、多级代理 |
| 选品 | 更多平台、更多线路、自动成交 |
| 获客 | 更多通道、自动召回、线下 POS |
| AI | 自训、微调、Agent、A/B |
| 存储 | 分片、多活、数据湖 |
| 扩展 | 全球多活、边缘、自治 |
| 合规 | GDPR、CCPA、PIPL、跨境传输落地细则 |
| 生态 | 供应链、金融 |

```text
auth.sso = false
auth.mfa = false
payment.raas = false
selection.auto_deal = false
acquisition.social = false
acquisition.ecommerce = false
acquisition.expo = false
acquisition.agency = false
ai.agent = false
ai.finetune = false
digital_human = false
geo_seo = false
raas = false
global_multi_active = false
```

**状态机**

```text
User:     pending → active → suspended → deleted
Payment:  created → pending → succeeded → failed → refunded
Report:   draft → analyzing → completed → acquired
Task:     created → running → paused → completed → failed
Lead:     new → scored → qualified → contacted → replied → won → lost → recalled
Campaign: draft → scheduled → sending → sent → paused → completed
Recall:   triggered → queued → delivered → recovered → failed
```

**UI 占位：** 登录页 SSO 置灰；支付页 RAAS 入口；选品页自动成交；获客页社交 / 电商 / 展会 / 代理 Tab；AI 页 Agent / 微调；看板八率 + 五时效；设置里合规、审计、删除。

**接口占位**

```http
POST /auth/sso
POST /payments/raas
POST /selection/auto-deal
POST /acquisition/social
POST /acquisition/ecommerce
POST /acquisition/expo
POST /acquisition/agency
POST /ai/agent
POST /ai/finetune
POST /digital-human/generate
POST /geo/seo
POST /raas/settle
GET  /global/health
```

**留白验收：** 入口可见、接口可调、数据可存、事件可发、开关可控、降级可用、合规可审、扩展字段可加。占位接口不得写入生产账本，不得发送真实触达。

---

## 8. 4S 回退策略

回退是架构能力：先落地第一版 4S；不满意时恢复上一版代码与 DB。基线是本文件提交前的仓库状态（CloudBase 云文档方案，见 `back.md`）。

### 8.1 总原则

1. **代码：** 每次 4S 变更有 Git Tag、Release、镜像版本。
2. **DB：** 每次 Schema 变更有 Forward + Rollback。
3. **配置：** Feature Flag、环境变量、路由可一键切换。
4. **流量：** 网关按租户 / 百分比 / 版本切流。
5. **事件：** 契约向后兼容；消费者可重放。
6. **AI：** 模型、Prompt、路由、缓存版本化。
7. **数据：** 关键表有快照、PITR、逻辑备份。
8. **状态：** 支付、线索、任务、召回可补偿，不靠手工改行。
9. **观测：** 回退前后对比八率、五时效、错误率；自动告警。
10. **决策：** 触发阈值满足即回退，不在故障版本上加功能。

### 8.2 S1 Scenario

版本化对象：PRD、用户故事、流程图、状态机、KPI、API 契约、事件契约、数据字典、风控、合规清单。

Tag：`s1-v1.0.0`。回退用 `git revert` 或检出该 Tag，并列出受影响的 S2 / S3 / S4。触发：KPI 定义无法复算、场景遗漏、合规风险、技术不可行。产物：上一版契约、影响报告、回退计划。

### 8.3 S2 Service

版本化对象：服务代码、镜像、Helm / K8s、网关路由、BFF、依赖、事件契约、Feature Flag。

Tag：`s2-v1.0.0`。镜像：`pickglobal/<service>:1.0.0`。

| 策略 | 用法 |
| --- | --- |
| 蓝绿 | 两套环境，切流回旧 |
| 金丝雀 | 按百分比；异常即停 |
| 滚动回退 | `kubectl rollout undo` |
| 影子流量 | 新版本只观察 |
| 功能开关 | 关新功能，留旧逻辑 |
| 降级 | 新域失败则走旧模块 |

触发：错误率 &gt;1%；P95 &gt;2×；可用性低于阶段目标；支付失败率 &gt;0.5%；送达率 &lt;95%；bounce &gt;1.5%；complaint &gt;0.1%。

### 8.4 S3 Storage

每个 migration 同时提交 `up.sql` 与 `down.sql`。禁止无回滚的删列、改类型、丢数据。大表用 Expand-Contract。变更前 `pg_dump` + WAL 可恢复到变更点。先在只读副本验证回退。

```sql
-- up.sql
ALTER TABLE leads ADD COLUMN score_v2 numeric;
-- down.sql
ALTER TABLE leads DROP COLUMN score_v2;
```

| 策略 | 用法 |
| --- | --- |
| Forward + Rollback | 每个 migration 有 down |
| Expand-Contract | 先加字段，再迁移，再删旧字段 |
| 双写 | 新旧表同时写，切回旧表 |
| 视图兼容 | 新表用视图保住旧读 |
| 快照 / PITR | 变更前全量；按时间点恢复 |
| 影子表 | 新表影子写，验证后切换 |

Expand-Contract：加 `score_v2` → 双写 → 读切到新列 → 再删旧列。回退时加回旧列、从 `score_v2` 回填、再删新列。触发：migration 失败、数据不一致、查询变慢 &gt;2×、锁表 &gt;5s、支付或线索异常、KPI 断档。

```bash
pg_dump -Fc pickglobal > pickglobal_before_s3.dump
pg_restore -d pickglobal pickglobal_before_s3.dump
```

PITR：`recovery_target_time` 指到变更前。恢复后跑数据校验（租户行数、账本合计、`leads` 唯一键）。

### 8.5 S4 Scale

版本化：副本数、分片规则、缓存、CDN、限流、降级、多活、同步、成本模型。配置目录 `config/s4-v1.0.0`。回退是切回上一版配置、HPA 副本、网关限流、Redis 策略、CDN 规则、消费者并发。分片规则一旦有数据落入新片，回退走双写与只读校验，不直接删片。触发：CPU 或内存 &gt;80% 且扩容无效、P95 &gt;2×、错误率 &gt;1%、成本超预算、分片倾斜、缓存穿透、多活延迟超阈值。

### 8.6 代码、配置、流量、事件、AI

```text
main
  ├── release/s1-v1.0.0
  ├── release/s2-v1.0.0
  ├── release/s3-v1.0.0
  └── release/s4-v1.0.0
```

Tag 格式 `s{1-4}-v{major}.{minor}.{patch}`。Release 分支保护；PR 需要 Review；CI 通过后才部署；CD 必须能回退。流水线：Build → Test → Scan → Deploy → Verify → Release，Verify 失败进入 Rollback。

```bash
kubectl rollout undo deployment/user-service
helm rollback user-service 1
```

配置按 `config/s1-v1.0.0` … `config/s4-v1.0.0` 存放，支持一键、灰度、按租户、按区域、按百分比回退。Flag 默认值见 §7。

流量按版本、租户、百分比、区域、设备切回上一版选择器。事件信封：

```json
{ "event": "lead.discovered", "version": "1.0.0", "tenant_id": "t1", "payload": {} }
```

消费者同时接受当前版与上一版。失败进死信。回放只重放业务幂等事件，支付与发信以 `idempotency_key` / `provider+event_id` 去重。

AI 回退对象：模型、Prompt、路由、缓存、参数、评估集。切回上一版或降级到规则。触发：解释与规则金额偏差 &gt;5pt、延迟超预算、成本超预算、合规风险。

### 8.7 决策矩阵

| 变更 | 回退方式 | 时间 | 触发 |
| --- | --- | --- | --- |
| S1 需求 | Git revert / 检出 Tag | 分钟 | KPI 不可复算、合规风险 |
| S2 服务 | 开关 / 金丝雀停 / rollout undo | 秒 | 错误率 &gt;1%，P95 &gt;2× |
| S3 DB | migration down；不行则快照 / PITR | 分钟 | 数据异常、锁表、KPI 断档 |
| S4 扩展 | 配置中心切回 | 秒 | 性能下降、成本超预算 |
| 支付 | 切回旧支付版本并停新单 | 秒 | 失败率 &gt;0.5% |
| AI | 切回旧模型或规则 | 秒 | 金额偏差、延迟、合规 |
| 事件 | 停消费者、修契约、按时间重放 | 分钟 | 消费积压或重复入账 |

### 8.8 第一版落地与回退

1. **设计：** S1 契约与 KPI；S2 模块与接口；S3 Schema + up/down；S4 容量、限流、Flag。
2. **实现：** Tag `s1-v1.0.0`–`s4-v1.0.0`；migration up；配置入库；部署。
3. **验证：** 功能、八率五时效可算、红线、合规、成本。
4. **不满意：** 关 Flag → 切流量 → rollout undo → migration down 或 PITR → 事件按幂等重放 → AI 切回规则。
5. **回退后：** 登录与旧数据可读、账本合计一致、看板可算、无新告警，再写根因。

### 8.9 检查清单

- 代码：Git Tag、镜像 Tag、Helm Release、rollout undo、Feature Flag
- DB：`up.sql`、`down.sql`、变更前快照、PITR、行数与账本校验
- 配置：配置版本、Flag、环境变量、路由
- 流量：网关切流、蓝绿、金丝雀、影子
- 事件：版本号、上一版兼容、重放、死信
- AI：模型版本、Prompt 版本、路由版本、规则降级
- 观测：Trace、Metrics、Log、Audit、告警（含送达红线与 ActT/RecT P95&gt;72h）

### 8.10 落地命令

可执行回退在 [rollback/](rollback/)。基线是 CloudBase 云文档（`backend/db/store.py` 的 JSON 集合）。PostgreSQL 形态只存在于 `migrate-up` 之后；`migrate-down` 或 PITR 把它收回 `analysis_reports`、`outreach_messages`、`payment_orders`、`activation_jobs`、`recall_jobs`。

```bash
./rollback/rollback.sh pin-tag --repo .
./rollback/rollback.sh migrate-up --store backend/data/store.json --journal rollback/state/wal.jsonl
./rollback/rollback.sh run --store backend/data/store.json --home rollback/state --journal rollback/state/wal.jsonl --events rollback/state/events.jsonl
```

`run` 的顺序：关闭 Flag、流量切回 `baseline-cloudbase`、migration down、down 失败则 PITR 到最近一条 CloudBase WAL、事件按 `idempotency_key` / `provider+event_id` 重放两次且第二次不得改账本、AI 偏差超过 5pt 时改回规则引擎。代码回退默认只打印计划；`--apply` 才 `git checkout baseline-cloudbase -- <路径>`，不 reset、不移动已有标签，也不回退 `rollback/` 与 `project.md`。

JSON 库里 API 已经直接写入的 `payments`、`recalls`、`kpi_metrics` 不会被 up/down 吞掉。只有从 CloudBase 旧集合搬过去的文档会在 down 时搬回来；两边主键相同的文档各自留在原集合。PostgreSQL 实例上的表用 `backend/db/sql/0001_core/down.sql` 删除，不改 JSON 文件。

**回退标准：** 代码用 Git / 发布系统秒级回到上一镜像；DB 用 down / 快照 / PITR 分钟级回到上一 Schema 与数据；配置与流量秒级切回；事件与支付幂等，避免回退本身造成双发或双记账。
