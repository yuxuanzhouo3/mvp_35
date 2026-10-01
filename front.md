# PickGlobal 多端界面适配

一套 4S，多端渲染。S1 场景统一，S2 服务复用，S3 存储统一，S4 按端扩展。支撑 Web / iOS / Android / iPad / 微信小程序 / Mac / Win。每端有功能边界、交互适配和回退。

产品仍是两条路径：选品与分析报告，九路获客（线索 → 成交 → 召回）。金额由规则引擎计算，触达须人工批准。产品 KPI、服务域与主库以 [project.md](project.md) 为准；本文规定客户端怎么呈现、怎么降级、怎么回到上一版。

当前仓库里的 `front/` 是 Next.js Web 壳：`/` 官网，`/workspace` 工作台。手机底栏、iPad 分栏、小程序 Tab、分端 BFF 按本文落地，未单独发版。

---

## 1. 多端适配总原则

1. **一套 4S，多端渲染。** S1 场景统一，S2 服务复用，S3 存储统一，S4 扩展按端分流。
2. **响应式 + 自适应 + 原生增强。** 手机用响应式加原生能力；iPad 用分栏、拖拽和手写；小程序用轻量页加微信生态。
3. **核心链路一致。** 登录、支付、选品、报告、获客、KPI 全端同一套业务结果。
4. **交互降级。** 小屏走步骤式；大屏走工作台式。
5. **能力占位。** 每端预留推送、相机、通讯录、日历、文件接口。未接通时入口可见、调用返回占位，不改主链路。
6. **回退一致。** 每端都有版本号、灰度、降级、回退。
7. **数据一致。** PostgreSQL 是主存储。端侧只做缓存。
8. **安全一致。** JWT / OAuth2 / RBAC / RLS 全端统一。查询带 `tenant_id`。

---

## 2. 4S 功能设计

### 2.1 S1 Scenario 场景 / 需求

**多端场景**

| 端 | 核心场景 | 交互特征 |
| --- | --- | --- |
| 手机 | 随时查看、快速获客、消息回复 | 单列、底部导航、手势 |
| iPad | 选品分析、报告阅读、批量获客 | 分栏、拖拽、手写 |
| 微信小程序 | 轻量登录、分享、裂变、召回 | 微信登录、分享、订阅消息 |
| Web | 工作台、看板、批量管理 | 多栏、表格、图表 |
| Mac / Win / Linux | 专业分析、批量操作 | 多窗口、快捷键 |
| iOS / Android | 推送、相机、通讯录 | 原生能力 |

**统一功能场景**

1. 登录 / 注册 / 支付
2. 自有导入 / 帮我选品
3. 路线和市场设定
4. 选品分析报告
5. 一键获客
6. 获客任务管理
7. 线索 / 成交 / 召回
8. KPI 看板
9. AI 内容 / 数字人
10. RAAS / 代理 / 渠道

场景 2–5 属于路径 A，6–7 与 10 属于路径 B，8 是八率 + 五时效。冷客启动和流失召回留在路径 B，不开第三条产品线。

**多端 KPI**

手机、iPad、小程序使用同一组 S2 目标。分母为 0 时显示「—」。完整八率（利润率、行动率、线索合格率、冷客激活率、召回成功率）与口径见 [project.md](project.md)。

| KPI | 手机 | iPad | 小程序 |
| --- | --- | --- | --- |
| 分析时效 AnaT | ≤2 min | ≤2 min | ≤2 min |
| 线索时效 LeadT | ≤3 min | ≤3 min | ≤3 min |
| 获客时效 AcqT | ≤3 天 | ≤3 天 | ≤3 天 |
| 激活时效 ActT | ≤24h | ≤24h | ≤24h |
| 召回时效 RecT | ≤24h | ≤24h | ≤24h |
| 触达率 TR | ≥95% | ≥95% | ≥95% |
| 打开率 OR | ≥40% | ≥40% | ≥40% |
| 获客率 AR | ≥8% | ≥8% | ≥8% |

**S1 回退**

- PRD 版本化：`s1-v1.0.0`
- 多端场景清单版本化
- KPI 定义版本化
- 回退：Git Revert

### 2.2 S2 Service 服务 / 架构

MVP / SVP 仍是 FastAPI 模块化单体。下面的 BFF 是按端适配的契约：同一核心服务，不同聚合与字段裁剪。Business 阶段再按端拆部署。

```text
Client
  ├── Web
  ├── iOS
  ├── Android
  ├── iPad
  ├── 微信小程序
  ├── Mac
  ├── Win
  └── Linux

API Gateway
  ├── Auth
  ├── Rate Limit
  ├── Routing
  ├── WAF
  └── Audit

BFF
  ├── Web BFF
  ├── Mobile BFF
  ├── iPad BFF
  ├── MiniProgram BFF
  └── Desktop BFF

Core Services
  ├── User Service
  ├── Payment Service
  ├── Product Service
  ├── Selection Engine
  ├── Report Service
  ├── Acquisition Service
  ├── Lead Service
  ├── Campaign Service
  ├── Recall Service
  ├── AI Model Service
  ├── GEO / SEO Service
  ├── Content Factory
  ├── Digital Human
  ├── Channel Service
  ├── RAAS Service
  └── Analytics Service
```

**BFF 职责**

| BFF | 职责 |
| --- | --- |
| Web BFF | 工作台、看板、批量 |
| Mobile BFF | 单列、推送、相机 |
| iPad BFF | 分栏、拖拽、手写 |
| MiniProgram BFF | 微信登录、分享、订阅消息 |
| Desktop BFF | 多窗口、快捷键 |

**多端接口适配**

```http
GET /api/v1/mobile/home
GET /api/v1/ipad/workbench
GET /api/v1/miniprogram/home
GET /api/v1/web/dashboard
GET /api/v1/desktop/workbench
```

这些路由返回该端首屏需要的聚合。写入仍走核心接口（商品、分析、报告、获客、线索），避免每个端各写一套账。

**多端能力占位**

- 推送：APNs、FCM、微信订阅消息
- 相机：扫码、OCR、拍照
- 通讯录：邀请、代理
- 日历：预约、提醒
- 文件：导入、导出
- 分享：微信、LinkedIn、Facebook

**S2 回退**

- 服务版本：`s2-v1.0.0`
- 镜像 Tag：`pickglobal/mobile-bff:1.0.0`（Web / iPad / 小程序 / Desktop 同规则）
- Helm Rollback
- K8s Rollout Undo
- Gateway 切流

### 2.3 S3 Storage 数据 / 存储

主库是 PostgreSQL。报告文件、导入文件进对象存储，库里留 key。端上的 SQLite、MMKV、Storage、IndexedDB 只缓存，可清空后从云端重建。

**多端数据表**

```sql
-- 设备
devices(id, tenant_id, user_id, platform, device_id, push_token, created_at)

-- 端配置
client_configs(id, platform, version, config jsonb, created_at)

-- 多端会话
sessions(id, tenant_id, user_id, platform, token, expires_at)

-- 多端事件
client_events(id, tenant_id, user_id, platform, event, payload jsonb, created_at)
```

`platform` 取值：`mobile`、`ipad`、`miniprogram`、`web`、`desktop`。iOS 与 Android 手机记 `mobile`，并在 `devices` 上区分系统。

**多端数据隔离**

- 业务行：`tenant_id` + `user_id` + `platform`
- RLS 按 `tenant_id`
- 端侧缓存：Redis + 本地缓存
- 端侧日志：`client_events`

**多端存储策略**

| 端 | 本地存储 | 云端存储 |
| --- | --- | --- |
| 手机 | SQLite / MMKV | PostgreSQL |
| iPad | SQLite / CoreData | PostgreSQL |
| 小程序 | Storage | PostgreSQL |
| Web | IndexedDB | PostgreSQL |
| Mac / Win | SQLite | PostgreSQL |

**S3 回退**

- Migration `up` / `down`
- 快照 `pg_dump`
- PITR
- 只读副本验证
- 双写 / 视图兼容

### 2.4 S4 Scale 扩展 / 优化

**多端扩展**

| 端 | 扩展方式 |
| --- | --- |
| 手机 | 原生 + 热更新 |
| iPad | 分栏 + 多任务 |
| 小程序 | 分包 + 按需加载 |
| Web | CDN + SSR |
| Mac / Win | 自动更新 |

**多端性能**

| 端 | 首屏 | 交互 | 包大小 |
| --- | --- | --- | --- |
| 手机 | ≤1.5s | ≤100ms | ≤50MB |
| iPad | ≤1.5s | ≤100ms | ≤80MB |
| 小程序 | ≤1s | ≤100ms | ≤2MB 主包 |
| Web | ≤1s | ≤100ms | ≤1MB |
| Mac / Win | ≤2s | ≤100ms | ≤150MB |

小程序总包 ≤20MB。Web 的 1MB 指首屏关键资源，图表与工作台按路由加载。

**多端缓存**

- CDN：静态资源
- Redis：接口缓存
- 本地：SQLite / MMKV / Storage
- 图片：WebP / AVIF

**多端限流**

- 按平台限流
- 按租户限流
- 按接口限流
- 按设备限流

**S4 回退**

- 配置中心回退
- Feature Flag
- Gateway 切流
- CDN 回退
- 小程序版本回退

---

## 3. 前端界面适配

交互只改呈现。登录结果、报告数字、线索状态、KPI 口径在各端相同。

### 3.1 手机

**首页。** 手机打开 `/` 时先识别端（浏览器、微信、小程序 WebView、Android / iOS 套壳、Electron / Tauri）。首屏只留一句承诺、四个样例数字，和拇指区的「开始分析」。原生安装包未发布前，手机继续用这个网页。

**布局**

- 单列
- 底部导航：首页、选品、获客、消息、我的
- 顶部：租户、搜索、通知
- 手势：下拉刷新、左滑、长按

**核心页面**

1. 登录：手机号 / 微信 / Apple
2. 首页：KPI 卡片、任务、快捷入口
3. 选品：导入、帮我选品、报告
4. 获客：任务、线索、成交、召回
5. 消息：站内信、推送、邮件
6. 我的：订阅、支付、设置

**原生能力**

推送、相机、通讯录、日历、文件、分享。

**适配**

安全区、暗黑模式、字体缩放、双指缩放、横屏、折叠屏。

### 3.2 iPad

**布局**

- 分栏：左侧导航 + 中间列表 + 右侧详情
- 拖拽：报告、线索、任务
- 手写：批注、签名
- 多任务：Split View、Slide Over
- 键盘：快捷键

**核心页面**

1. 工作台：KPI、任务、报告
2. 选品：导入、分析、报告
3. 获客：任务、线索、成交、召回
4. 看板：八率 + 五时效
5. AI：内容、数字人
6. 设置：订阅、支付、团队

**适配**

分栏、拖拽、手写、双指缩放、键盘、触控板、外接屏。

### 3.3 微信小程序

**布局**

- 单列
- 底部 Tab：首页、选品、获客、我的
- 微信导航栏
- 订阅消息

**核心页面**

1. 登录：微信一键登录
2. 首页：KPI、任务、分享
3. 选品：导入、帮我选品、报告
4. 获客：任务、线索、召回
5. 我的：订阅、支付、邀请

**微信能力**

微信登录、微信支付、分享、订阅消息、客服消息、群工具、小程序码。

**适配**

分包、按需加载、主包 ≤2MB、总包 ≤20MB、暗黑模式、字体缩放。

### 3.4 Web

**布局**

多栏、表格、图表、批量操作、快捷键。

**核心页面**

登录、工作台、选品、获客、看板、AI、设置。

**适配**

响应式、SSR、CDN、PWA。

现有 `front/` 即这一端：官网 `/`，工作台 `/workspace`（看板、选品分析、获客经营）。手机宽度先收成单列；iPad 宽度在同一 Web 壳里预留分栏，原生拖拽和手写留给 iPad 客户端。

### 3.5 Mac / Win

**布局**

多窗口、快捷键、菜单栏、托盘。

**核心页面**

工作台、选品、获客、看板、设置。

**适配**

自动更新、原生菜单、文件系统、通知。

---

## 4. 多端回退策略

### 代码回退

| 端 | 回退方式 |
| --- | --- |
| 手机 | 热更新 / 商店回退 |
| iPad | 热更新 / 商店回退 |
| 小程序 | 版本回退 / 灰度 |
| Web | Git Revert / CDN 回退 |
| Mac / Win | 自动更新回退 |

### DB 回退

Migration `down`、快照、PITR、只读副本。

### 配置回退

配置中心、Feature Flag、按平台回退。

### 流量回退

Gateway 切流、按平台切流、按版本切流。

### 小程序回退

版本回退、灰度发布、分包回退、配置回退。

任一端回退只撤该端的渲染、配置和流量。PostgreSQL 里的商品、报告、线索保持可核对。Schema 回退走带 `down` 的 migration。

---

## 5. 多端功能占位与留白

| 模块 | 手机 | iPad | 小程序 | Web | Mac/Win |
| --- | --- | --- | --- | --- | --- |
| 登录 | 手机号 / 微信 / Apple | 手机号 / 微信 | 微信 | 邮箱 / OAuth | 邮箱 / OAuth |
| 支付 | Apple / 微信 / 支付宝 | Apple / 微信 | 微信支付 | Stripe / PayPal | Stripe / PayPal |
| 选品 | 单列 | 分栏 | 单列 | 多栏 | 多窗口 |
| 报告 | 卡片 | 分栏 | 卡片 | 表格 | 多窗口 |
| 获客 | 任务 | 拖拽 | 任务 | 批量 | 批量 |
| 看板 | 卡片 | 分栏 | 卡片 | 图表 | 图表 |
| AI | 对话 | 分栏 | 对话 | 工作台 | 工作台 |
| 推送 | APNs / FCM | APNs | 订阅消息 | Web Push | 原生 |
| 相机 | 原生 | 原生 | 微信 | 浏览器 | 原生 |
| 分享 | 原生 | 原生 | 微信 | 链接 | 原生 |
| 通讯录 | 原生 | 原生 | 微信 | 导入 | 原生 |
| 日历 | 原生 | 原生 | 微信 | 日历 | 原生 |
| 文件 | 原生 | 原生 | 微信 | 上传 | 原生 |

国内首期支付以微信为主，Web 扫码与微信内 JSAPI 已在后端方案中留 adapter。表中的 Apple、支付宝、Stripe、PayPal 是端能力占位，按 Flag 打开，不并行记两套账。

**留白**

折叠屏、车机、手表、TV、AR / VR、语音助手、离线模式。

---

## 6. 多端交付时间线

| 阶段 | 时间 | 用户 | 端 |
| --- | --- | --- | --- |
| MVP | 1 week | <1k | Web + 手机 |
| SVP | 2 week | <1w | Web + 手机 + 小程序 |
| Business 1-10 | 1 month | <10w | Web + 手机 + iPad + 小程序 |
| Speed up 1 | 2 month | <100w | 全端 |
| Speed up 2 | 3 month | <1000w | 全端 + 多活 |
| Speed up 3 | 1 year | <1E | 全端 + 全球 |

MVP 的「手机」先用现有 Web 响应式：单列、安全区、底部导航。原生壳、热更新和小程序分包从 SVP 起单独交付。

---

## 7. 一句话总结

更新后的 4S 以手机 + iPad + 微信小程序为核心多端适配：S1 统一场景，S2 用 BFF 按端适配，S3 用 PostgreSQL 统一存储，S4 按端扩展。每端都有独立版本、灰度、降级、回退。第一版 4S 不满意时，代码、DB、配置、流量、小程序版本都能回到之前的状态。
