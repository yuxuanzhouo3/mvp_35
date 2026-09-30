# PickGlobal 全栈核心能力

本文权威顺序：

1. **功能拆解**（产品要什么）  
2. **量化 KPI**（做得好不好）  
3. **技术架构 · 4S**（怎么设计兑现功能 + KPI，以及流量/功能变多怎么扩）  

| S | 含义 | 核心问题 | 典型内容 |
| --- | --- | --- | --- |
| **1. Scenario** | 场景 / 需求 | 系统要做什么？ | FR / NFR、QPS、DAU、Latency、Availability |
| **2. Service** | 服务 / 架构 | 由哪些服务组成？ | Client、API Gateway、Service、Cache、DB、MQ、Object Storage |
| **3. Storage** | 数据 / 存储 | 数据怎么存、怎么访问？ | Schema、SQL/NoSQL、Index、Partition、Replication、Cache |
| **4. Scale** | 扩展 / 优化 | 流量变大？功能变多？ | LB、Sharding、Caching、CDN、Async、Replication、Failover |

对齐 [project.md](project.md) / [front.md](front.md) / [back.md](back.md) / [admin.md](admin.md)。

## 硬约束

| 项 | 锁定 |
| --- | --- |
| 全栈 | Next.js 16 + TypeScript + Tailwind + shadcn/ui · Python FastAPI · CloudBase |
| AI | 腾讯混元主模型；通义仅备份默认关；不上 OpenAI / Claude / Gemini |
| 基建 | 仅国内腾讯云 |
| 选品主数据（路径 A） | MVP：手动 / CSV / 国内货源 API |
| 获客（路径 B） | 九路 provider；DEMO 可 mock；海外正式开通前过合规 |
| 数智人 | DEMO placeholder；不买 10h 包 |
| DB | `<10 万` 只云文档；`≥10 万` 才加 MySQL |

---

## 0. 总览

对外只有 **两条产品路径**。冷客启动 / 流失召回是路径 B 的生命周期阶段，不是第三条产品线。

```text
【A】选品与分析报告 →「一键获客」跳进 B
【B】九路获客 → 触达成交 → 冷客启动 / 流失召回
      ↑_______________ 反馈回流商品判断与线索分 _______________|
```

| 产品 | 功能模块（用户可见） | 代码边界（实现） |
| --- | --- | --- |
| **A** | 双向入口 · 路线市场 · 分析引擎 · 报告+一键获客 | `app/products` · `app/analysis` |
| **B** | 九路获客经营（含成交/召回） | `app/leads` · `app/campaigns` · `providers/*` · `app/activation` · `app/recall` |

B 在代码上拆「常规触达 / 冷启召回」两套规则与 job（共用 SES / suppression / `leads`），对外仍只说路径 B。

---

## 1. 功能拆解（对外锁定）

### 一、软件选品和生成分析报告 · 路径 + 特色

```text
双向入口 → 路线与市场设定 → 选品分析引擎 → 选品报告
                                              ↓
                                    【一键获客】跳转获客板块（路径 B）
```

| # | 功能 | 路径 | 特色 |
| --- | --- | --- | --- |
| **A1** | **双向选择入口** | **自有导入**（表单/CSV）**或「帮我选品」**（国内货源目录） | 两条入口汇入同一 `products`；不绑死外部电商选品主库 |
| **A2** | **路线和市场设定** | 货源地 / 目标市场 / 物流路线 / 税务口径 / 售价币种 | MVP 默认：货源 CN、目标 US、中美税、成本 CNY / 售价 USD；可扩展中港/中澳 |
| **A3** | **选品分析引擎** | 异步 job：规则算利润·税务·时效·风险 → 混元只做解释 | 金额可审计；混元不能改数；`Decimal` + 版本快照 |
| **A4** | **输出选品报告** | 四维报告 + CTA **「一键获客」** → 跳转路径 B，携带 `seed_analysis_id` | 报告不是终点；抬行动率 ActR |

说明：Amazon 等电商平台优先作 **路径 B 线索源**，不作路径 A 选品主库。若未来做「店内选品」，另开 `ProductCatalogProvider`。

### 二、软件帮人获客 · 路径 + 特色

统一漏斗（九路共用）：

```text
线索获客 → 触达 → 成交标记 → 冷客启动 或 流失召回
```

分层：

```text
1–5 = 主获客
6–8 = 优化（供 1–5 用；销售本品也能用）
6–9 = 可用来销售 PickGlobal 本身
```

| # | 路径 | 闭环 | 分层 | 特色 |
| --- | --- | --- | --- | --- |
| **B1** | **电商平台** Amazon · Temu · Walmart · 淘宝 · 拼多多 | 线索获客 + 成交 + 召回 | 主获客 | 访客/询盘/订单买家/沉默买家统一进 `leads` |
| **B2** | **社交平台** LinkedIn · Facebook · 微信小程序 · 抖音 · 小红书 · 快手 | 线索获客 + 成交 + 召回 | 主获客 | 公域互动沉淀；小程序可同栈登录 |
| **B3** | **线上展会平台** | 线索获客 + 成交 + 召回 | 主获客 | 会期削峰；会后进冷启/召回 |
| **B4** | **12 代理渠道** | 批量获客 + 成交 + **分成** | 主获客 | 渠道子账户；账本与分成分离 |
| **B5** | **智慧大脑大数据** 企查查 + 天眼查 + etc | 线索集合 + 成交 + 召回 | 主获客 | 去重、质量分、合规留痕 |
| **B6** | **GEO / SEO** | 线索获客 + 成交 + 召回 | 优化；可自销 | 供 1–5；落地页归因 |
| **B7** | **AI 内容工厂 + 数字人 + 线下客流** | 线索获客 + 成交 + 召回 | 优化；可自销 | 供 1–5；数智人 placeholder |
| **B8** | **跨境元素复现** | 线索获客 + 成交 + 召回 | 优化；可自销 | 约 **80%** 中美/中港/中澳 + **20%** 内陆 |
| **B9** | **RaaS** | 官网成功抽成 + APP 账户销售（类比 elink） | 本品销售 | 卖结果抽成；ledger 与套餐可并存 |

硬规则：

- 统一 `leads` + `source_channel`。  
- 触达默认：**AI 生成 → 人工批准 → 发送**。  
- 冷启/召回：**规则入队**，混元只写文案。  
- 海外平台正式开通前过合规；DEMO 用 mock。  
- B4 / B9 金额：整数分、幂等账本、验签后才发佣/记抽成。

---

## 2. 量化 KPI · 做得好不好

### 2.1 口径原则

- 金额只用规则引擎，不用混元估算。  
- 默认滚动 **30 天**。分母为 0 → `—`。  
- 对外用租户**中位数**。

### 2.2 八率 + 五时效（唯一清单）

**八率**

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

红线：送达率（按封）≥95%；bounce&lt;1.5%；complaint&lt;0.1%。

**五时效（P50；超时记失败）**

| # | 指标 | 代号 | 主要服务功能 | 公式 | S2 |
| --- | --- | --- | --- | --- | --- |
| 1 | 分析时效 | `AnaT` | A3 | 完成 − 请求 | ≤2 min |
| 2 | 线索时效 | `LeadT` | B 发现 | discovery 成功 − 发起 | ≤3 min |
| 3 | 获客时效 | `AcqT` | B 成交 | first_W − first_delivered（仅 W） | ≤3 天 |
| 4 | 激活时效 | `ActT` | B 冷启 | 首封 delivered − 入队 | ≤24 h |
| 5 | 召回时效 | `RecT` | B 召回 | 首封 delivered − 触发 | ≤24 h |

```text
A = approve 受众 − suppressed/bounced/无邮箱
D = A 中至少 1 封 delivered
W = 触达后 14 天内 replied 或赢单/约见
```

看板：**首屏四率 + 北星 AR**；时效条可折叠；红线限流；ActT/RecT 的 P95&gt;72h 告警。

### 2.3 利润公式

```text
R = target_price_usd
C = 采购折USD + 包装 + 国内段 + 国际段
F = R × (platform_fee_rate + payment_fee_rate)
T = 关税等
N = R − C − F − T     → 利润率 N/R
```

落库：`net_margin`、`net_profit_usd`、`fx_usd_cny`、`rules_version`。

### 2.4 功能 → KPI 验收对照

| 功能 | 必看 KPI | 过线信号（S2） |
| --- | --- | --- |
| A1 双向入口 | 导入成功率；目录搜索可用性 | 手动+CSV+mock 目录均可入库 |
| A2 路线市场 | 报告含正确 market/route 快照 | 改市场后必须重算才出新报告 |
| A3 分析引擎 | `N%` · `AnaT` | 关混元仍有 metrics；P50≤2min |
| A4 报告+一键获客 | `ActR` | ≥50%；携带 `seed_analysis_id` |
| B1–B5 主获客 | `QR` · `LeadT` · `AR` | QR≥60%；LeadT≤3min；AR≥8% |
| B 触达 | `TR` · `OR` · 送达红线 | TR≥95%；OR 辅助；bounce/complaint 红线 |
| B 冷启/召回 | `ActR_cold` · `RecR` · `ActT` · `RecT` | 激活/召回率达标；P50≤24h |
| B4 / B9 分成抽成 | 账本对账成功率 | 仅验签后入账；幂等不双发 |

---

## 3. 技术架构 · 4S（兑现功能 + KPI）

4S 回答两件事：**现在怎么做成 A/B**，以及 **用户变多 / 九路变多时怎么扩**。  
功能清单见 §1，验收数字见 §2。

### 3.1 Scenario · 系统要做什么

#### 功能需求（FR）

| 路径 | 用户场景 | 系统必须完成 | 成功跳转 |
| --- | --- | --- | --- |
| **A1** | 自有导入 / 帮我选品 | 两条入口写入同一 `products` | 可进入 A2 |
| **A2** | 设货源、市场、路线、税务 | 冻结分析上下文（CN→US 默认） | 可进入 A3 |
| **A3** | 点「开始分析」 | 规则算 N/税/时效/风险；混元只解释 | `AnaT`≤2min；关混元仍有 metrics |
| **A4** | 看报告并点「一键获客」 | 只读报告 + 携带 `seed_analysis_id` 进 B | 抬 `ActR` |
| **B1–B5** | 从电商/社交/展会/代理/大数据找人 | provider 归一化进统一 `leads` | `QR`≥60%；`LeadT`≤3min |
| **B 触达** | 生成并批准后发送 | AI→人工批准→SES/渠道；禁未审群发 | `TR`≥95%；送达红线 |
| **B 成交** | 标记回复/赢单 | `W` 定义固定；账本幂等 | `AR`≥8%；`AcqT`≤3天 |
| **B 冷启/召回** | 未互动激活 / 互动后沉默 | 规则入队，混元只写文案 | `ActR_cold`/`RecR`；P50≤24h |
| **B6–B8** | 给 1–5 加权，或卖本品 | 归因/内容包/跨境模板挂在同一漏斗 | 不新开产品线 |
| **B9** | 官网/APP 成功抽成 | 验签后入 raas ledger | 与套餐并存；不污染普通 AR |

#### 非功能需求（NFR）

| 项 | MVP / S1（&lt;1 万卖家） | S2（~10 万） | S3a（~100 万，仍云托管） |
| --- | --- | --- | --- |
| **用户** | 注册卖家账号；MAU ≈ 15–25% | 同左 | 同左 |
| **可用性** | 单环境云托管；可短维护窗 | 多副本；同地域多实例 | 打满副本 + 网关/WAF |
| **同步 API Latency** | P95 ≤ 500ms（CRUD/查询） | P95 ≤ 400ms | P95 ≤ 300ms + 缓存 |
| **长任务 SLA** | 分析 P50≤5min；发现≤5min | **AnaT≤2min；LeadT≤3min** | 同 S2；P95 告警 |
| **分析 QPS** | 低：人点按钮；异步削峰 | 配额 + worker 副本 | 队列分 Topic |
| **发信吞吐** | SES sandbox / 小流量 | 限速 + 独立 IP 视投诉 | 资源包 + 多 IP |
| **安全** | HTTPS；密钥不出浏览器；租户隔离 | 同左 + 对账 | WAF、审计、密钥轮转 |
| **合规** | 海外平台 mock；国内 enrichment 可真接 | 分批过 ToS / 出境评估 | 按通道独立配额 |

工作台 IA（Scenario 对应页面）：

```text
工作台
├── 选品分析（A1–A4）自有导入 | 帮我选品 | 路线市场 | 报告→一键获客
└── 获客经营（B）通道 B1–B9 | 线索池/触达 | 成交分成/RaaS | 冷启动/召回
```

共性规则：长任务 `202 + jobs`；金额/评分/是否流失只由规则引擎算；`tenant_id` 强制；provider 可 mock 替换。

---

### 3.2 Service · 由哪些服务组成

```text
Client（Web / 五端 WebView 套同一官网）
  → API Gateway（同域 /api、/webhooks；CloudBase 网关鉴权）
  → FastAPI 模块化单体（非九个微服务）
       ├─ identity / tenant
       ├─ products / analysis          A1–A4
       ├─ leads / campaigns / providers B 发现+触达
       ├─ activation / recall          B 生命周期
       ├─ billing / raas               B4 / B9
       └─ metrics                      八率五时效快照
  → Worker（同镜像不同命令）
  → Cache（S2+ Redis）· MQ（MVP=jobs 集合；S2=TDMQ）
  → DB（云文档 → +MySQL）· COS
  → 混元 / SES / 位置服务 / 国内与海外 provider
```

| 组件 | 职责 | 兑现的功能 / KPI |
| --- | --- | --- |
| **Client** | Next.js 工作台 + mvp_30 壳 | A/B 全部 UI；SSE/轮询看时效 |
| **API Gateway** | 同域路由、用户鉴权、限流 | 浏览器不直连 DB/密钥 |
| **products/analysis** | 双向入口、市场设定、规则+混元 | A1–A4；`N%` `AnaT` `ActR` |
| **leads + providers** | 九路发现、去重、质量分 | B1–B8；`QR` `LeadT` |
| **campaigns + SES worker** | 草稿/批准/发送/webhook | `TR` `OR` 送达红线 |
| **activation/recall** | 规则扫描 + 独立 job | `ActR_cold` `RecR` `ActT` `RecT` |
| **billing** | 套餐、分成、RaaS 抽成 | B4/B9 对账 |
| **Cache** | 会话、配额、热点报告/计划受众 | 降同步 Latency |
| **MQ / jobs** | 分析、发现、发信、召回削峰 | 保 AnaT/LeadT；展会峰值 |
| **Object Storage** | 报告 PDF、导入文件、数智人占位素材 | A4 导出 |

路径 A 服务链：

```text
A1 POST /products | /imports | /catalog/search
A2 写入 origin/target/incoterm/tax 上下文
A3 POST .../analyses → 202 → worker：规则 metrics → 混元摘要
A4 GET /analyses/{id}；CTA → /gtm?seed_analysis_id=
```

路径 B 服务链：

```text
LeadProvider.search → normalize/dedupe/score → leads
  → campaign 草稿 → approve → send jobs → SES
  → webhook → 成交标记
  → 日扫规则 → activation_jobs / recall_jobs
```

```python
class LeadProvider(Protocol):
    channel: str  # ecommerce|social|expo|agency|enrichment|geo_seo|content_dh|cross_border|raas
    async def search(self, query: LeadSearchQuery) -> LeadSearchResult: ...
```

| 功能 | Service / Provider | MVP |
| --- | --- | --- |
| B1 电商 | `providers/ecommerce/*` | mock → 分批合规 |
| B2 社交 | `providers/social/*` | mock → 分批 |
| B3 展会 | `providers/expo` | mock；峰值进 MQ |
| B4 代理 | 渠道导入 + billing 分成 | 子账户；验签后分佣 |
| B5 大数据 | 企查查/天眼查 + 位置服务 | 国内可先真接 |
| B6 GEO/SEO | 归因事件 → leads | 与 1–5 共用池 |
| B7 内容/数字人/线下 | 内容 job + DH placeholder + 扫码 | 数字人不阻塞发信 |
| B8 跨境元素 | 市场包（话术/时区/合规）挂 campaign | 80/20 模板 |
| B9 RaaS | 官网/APP 成功回调 → raas ledger | 单列看板，不混进普通 AR |

横切：CloudBase Auth v2；微信 API v3 验签；混元 SSE；`/webhooks/ses` 5s 验签应答。

---

### 3.3 Storage · 数据怎么存、怎么访问

选型（与 [project.md](project.md) 一致）：

| 规模 | 主库 | 辅 | Cache / MQ |
| --- | --- | --- | --- |
| **&lt;10 万** | **只云文档**（文档型，非 MySQL） | COS | 可无 Redis；jobs 集合轮询 |
| **≥10 万** | **MySQL**（账户/配额/任务）+ 云文档（报告 JSON） | COS | Redis + TDMQ |
| **&gt;100 万** | CDB/TDSQL-C 主从/分片 | 云文档仅配置 | Redis 集群 + 多 Topic |

原则：报告/线索/活动是文档+状态机 → 云文档合适；对账/分成/配额要 JOIN 与强一致 → 才上 MySQL。  
访问：`repository` 协议；业务禁止直连 CloudBase HTTP；查询强制注入 `tenant_id`；列表用游标，不用深 offset。

#### Schema（MVP 集合）

| 集合 | 服务功能 | 关键字段 / 访问 |
| --- | --- | --- |
| `products` / `product_sources` | A1 | `normalized_sku` 唯一；来源快照 COS key |
| `analysis_reports` | A3/A4 | `metrics` JSON；`rules_version`；只读历史 |
| `leads` | B 发现 | `source_channel`；`dedupe_key`；`quality_score` |
| `campaigns` / `outreach_messages` | B 触达 | `audience_snapshot`；`ses_message_id`；`purpose` |
| `activation_jobs` / `recall_jobs` | B 生命周期 | `enqueued_at`；`reason`；与 campaign 互斥 |
| `jobs` | 全异步 | `status+progress+steps`；算五时效 |
| `payment_orders` / `usage_ledger` / raas | B4/B9、配额 | 整数分；`idempotency_key` 唯一 |
| `metric_snapshots` | 看板 | 定时聚合八率五时效 |
| `webhook_events` | SES/支付 | `provider+event_id` 去重 |

A2 存在商品/报告上下文，不散落全局配置：`origin_country`、`target_market`、`incoterm`、`hs_code_hint`。改市场必须重算新报告。

#### Index / 分区 / 副本 / Cache

| 手段 | 用法 |
| --- | --- |
| **Index** | 全表 `tenant_id+created_at`；SKU/dedupe/ses_message_id/job status 唯一或组合索引 |
| **Partition** | S2+ 按 `tenant_id` 或时间窗拆热点集合；MySQL 按租户分库分表是 S3 信号 |
| **Replication** | 云文档由平台副本；MySQL S2 起只读副本服务看板 |
| **Cache** | S2：配额、计划、热点报告；看板读 `metric_snapshots` 不现场扫全表 |
| **对象** | 大文件只进 COS；DB 存 key + hash + MIME |

最小事件序（Storage 写入顺序，供 KPI）：

```text
product_analysis_* → lead_discovery_* / lead_upserted
→ campaign_approved(audience_snapshot)
→ outreach_delivered/opened/bounced/complained
→ lead_replied / lead_marked_won
→ activation_* / recall_*
→ metric_snapshots
```

---

### 3.4 Scale · 流量变大 / 功能变多怎么办

两条扩容轴：**流量（卖家变多）** 与 **功能（九路/市场变多）**。语言与仓库边界不变。

#### 流量变大

| 信号 | 动作 | 4S 手段 |
| --- | --- | --- |
| 官网静态/SSR 变慢 | CDN + 云托管加副本 | LB / CDN / Replication |
| 分析/发现 P95 升高 | worker 副本；先出 metrics 再等混元 | Async |
| 发信排队、投诉抬头 | TDMQ 分 Topic；限速；独立 IP | MQ / Failover |
| 云文档扫描贵、对账不清 | **S2 加 MySQL**；报告留文档 | Sharding 预备 + 职责拆分 |
| 看板打主库 | 只读副本 + `metric_snapshots` | Cache / Replication |
| ≈100 万托管吃紧 | 打满云托管（S3a） | LB |
| **&gt;100 万或 SLA 不够** | 同镜像迁 TKE；CDB 分片 | Sharding / Failover / WAF |

硬规则：≤100 万只用云托管；不上 Java；不上为拆而拆的微服务。

#### 功能变多（九路 / 市场 / 本品销售）

| 变化 | 怎么扩（不要新开产品线） |
| --- | --- |
| 多一个电商/社交平台 | 新 `LeadProvider` 实现；`source_channel` 加枚举；DEMO 先 mock |
| 展会峰值 | 只加 worker/队列容量，不改同步 API |
| 代理分成 / RaaS | 复用 billing ledger，加科目与验签回调 |
| GEO/SEO、内容工厂、跨境包 | **挂在 B 漏斗上的策略/归因模块**，不新建线索主表 |
| 新目标市场（港/澳） | A2 市场模板 + B8 话术/时区包；税务表版本化 |
| Admin / 多端 | 官网唯一 UI；壳只改 URL；Admin 另套权限，不复制业务库 |

#### 功能 × Service × Storage × KPI

| 功能 | 主 Service | 主 Storage | 必看 KPI |
| --- | --- | --- | --- |
| A1 双向入口 | products / catalog | `products` `product_sources` | 导入成功率 |
| A2 路线市场 | products 上下文 | 报告快照字段 | 改市场必须重算 |
| A3 分析引擎 | analysis worker | `analysis_reports` `jobs` | `N%` `AnaT` |
| A4 一键获客 | analysis → GTM | `seed_analysis_id` | `ActR` |
| B1–B5 发现 | LeadProvider | `leads` | `QR` `LeadT` |
| B 触达 | campaigns + SES | `outreach_messages` | `TR` `OR` 红线 |
| B 成交 | leads + billing | `won_at` / ledger | `AR` `AcqT` |
| B 冷启/召回 | lifecycle worker | `activation_jobs` `recall_jobs` | `ActR_cold` `RecR` `ActT` `RecT` |
| B4/B9 | billing | 幂等 ledger | 对账成功率 |

竞争力：A 分钟级可审计报告；B 统一线索池 + 可对账抽成。  
壁垒：规则版本回放、去重/发信信誉、渠道 ledger。

---

## 4. 交付顺序

1. 骨架：FastAPI + Auth + `db/` + `net/` + Docker + metrics 骨架  
2. **A1–A4**：双向入口 → 市场设定 → 分析引擎 → 报告+一键获客（先打通 ActR / AnaT / N%）  
3. **B 内核**：leads + campaign + SES sandbox（TR / OR / AR）  
4. **B5** 真接 enrichment；B1–B4 mock  
5. **冷启 + 召回**（ActR_cold / RecR / ActT / RecT）  
6. B6–B8 优化层；B4/B9 ledger  
7. 九路分批合规上线；硬化与 Admin  
8. 规模化：TDMQ / MySQL / 多副本；必要时 TKE  

验收节奏：S1 指标能算全；S2 中位数达标 + 红线限流。

---

## 5. 一句话标准

> PickGlobal 只做两件事：**A 选品分析报告（双向入口→市场设定→引擎→报告→一键获客）**，  
> **B 九路获客成交召回（1–5 主获客，6–8 优化可自销，9 RaaS）**；  
> 用八率五时效衡量好坏；用 4S（Scenario / Service / Storage / Scale）在国内云上把功能做成可审计、可对账、可随流量与通道扩容的系统。

细节接口以 [back.md](back.md) 为准；功能与 KPI 以本文 §1–§2 为准；架构以本文 §3 为准。
