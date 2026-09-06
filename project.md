# PickGlobal

**Oversea Market Selling** · 选品分析与出海获客全链路闭环

跨境卖家从选品（或自有商品）到分析、获客、触达、流失召回的一条技术闭环。本仓库为 **MVP 35**。

---

## 1. MVP 35

| 项 | 说明 |
| --- | --- |
| 项目 | MVP 35 |
| 产品名 | PickGlobal |
| 域名 | [pickgrobal.mornscience.top](https://pickgrobal.mornscience.top) |
| 定位 | Oversea Market Selling（海外市场销售） |
| 一句话 | 选品分析和出海获客全链路闭环 |

---

## 2. 全链路技术闭环

```
跨境选品 或 自有商品
        ↓
商品分析报告（利润空间 / 税务 / 时间 / 风险）
        ↓
跨境获客
        ↓
数字人邮件触达
        ↓
流失召回
```

| 环节 | 做什么 |
| --- | --- |
| 商品入口 | 跨境选品，或接入卖家自有商品 |
| 商品分析报告 | 利润空间、税务、履约时间、风险分析 |
| 跨境获客 | 面向目标海外市场找客、建联 |
| 数字人邮件 | 数字人驱动的邮件触达与跟进 |
| 流失召回 | 对沉默 / 流失客户做召回闭环 |

闭环目标：选品结论可执行，获客动作可触达，流失客户可召回。

### 2.1 实现范围（已锁定）

| 项 | 决策 |
| --- | --- |
| 深度 | 生产级 |
| 目标市场（首版） | 美国 + 中国 |
| 商品来源 | 手动 / CSV + Amazon Creators API + 自定义商品 API |
| 获客来源 | Google Places + 自定义线索 API |
| 触达 | AI 文案 + 腾讯云智能数智人视频 + 腾讯云 SES |

### 2.2 链路实现要点

1. **商品入口**：录入、CSV 导入、Amazon 拉取、自定义 API 适配器统一写入 `products`
2. **商品分析报告**：利润空间、US/CN 税务估算、履约时间、风险评分，写入 `analysis_reports`
3. **跨境获客**：Places / 自定义线索 → `leads`，可绑定商品与目标市场
4. **数字人邮件**：LLM 生成个性化文案 → 数智人渲染视频 → SES 发送，记录于 `outreach_messages`
5. **流失召回**：沉默规则触发 `recall_jobs`，自动再触达并回流打开 / 回复状态

---

## 3. 技术选型

| 方案 | 状态 | 覆盖范围 |
| --- | --- | --- |
| Vercel | 不采用 `[x]` | 不作为本项目托管与发布主路径 |
| 腾讯云 Tencent Cloud | 采用 `[✓]` | **Code + DB**（CloudBase） |

客户端与分发不走 Vercel，走 **cnwww** 多端与商店：

- Android / Mac / Windows / iOS
- 微信小程序
- 苹果 App Store

腾讯云侧承担：

- **Code**：业务与链路代码（CloudBase 云托管）
- **DB**：商品、报告、获客与召回数据（CloudBase PostgreSQL）

### 3.1 CloudBase 架构

```
客户端 (Web / 原生壳 / 小程序)
        ↓
CloudBase 云托管 (Next.js SSR standalone)
        ↓
PostgreSQL + COS + 异步 Jobs
        ↓
外部 Provider（Amazon / Places / Custom / LLM / 数智人 / SES）
```

| 组件 | 用途 |
| --- | --- |
| CloudRun（云托管） | Next.js 15 App Router，`output: 'standalone'` |
| PostgreSQL | 业务主库 |
| COS | 报告附件、数智人视频 |
| Cloud Functions / Jobs | 拉品、分析、渲染、发信、召回调度 |

### 3.2 外部 Provider

| 能力 | 接入 |
| --- | --- |
| Amazon 商品 | Amazon Creators API（PA-API 已弃用） |
| Google 获客 | Places Text Search + Place Details；邮箱需网站 enrichment |
| 自定义 API | 统一 adapter：`fetchProducts()` / `fetchLeads()` |
| 分析与文案 | LLM |
| 数字人视频 | 腾讯云智能数智人 API → COS |
| 邮件 | 腾讯云 SES `SendEmail` + 打开 / 退信回调 |

密钥全部走云托管环境变量，不进前端。

### 3.3 客户端交付顺序

| 阶段 | 交付 |
| --- | --- |
| Phase A | Web 全链路闭环可部署到 `pickgrobal.mornscience.top` |
| Phase B | Capacitor（Android / iOS）、Electron（Mac / Win）、微信小程序，复用同一后端 API |
| Phase C | 域名 HTTPS、SES 验证、渲染队列、税率版本化、监控限流 |

### 3.4 核心数据表

| 表 | 用途 |
| --- | --- |
| `products` | 选品 / 自有商品 |
| `product_sources` | amazon / csv / custom |
| `analysis_reports` | 利润、税务、时间、风险 JSON |
| `leads` | 海外客户线索 |
| `campaigns` | 获客 / 触达活动 |
| `outreach_messages` | 邮件草稿与发送记录 |
| `digital_human_assets` | 视频 / 形象任务 |
| `recall_jobs` | 流失召回任务与状态 |
| `provider_credentials` | 外部密钥引用（加密） |
| `audit_logs` | 操作与发送审计 |

### 3.5 仓库结构（拟建）

```
mvp_35/
├── app/                    # Next.js 页面与 API
├── components/
├── lib/
│   ├── db/
│   ├── analysis/
│   ├── providers/
│   └── jobs/
├── clients/
│   ├── capacitor/          # Android / iOS
│   ├── electron/           # Mac / Win
│   └── miniprogram/        # 微信小程序
├── cloudbase/
│   ├── Dockerfile
│   └── migrations/
├── .env.example
├── project.md
└── README.md
```

### 3.6 所需密钥

- CloudBase 环境 ID、云托管、PostgreSQL 连接串
- Amazon Creators API Credential
- Google Maps Places API Key
- 自定义商品 / 线索 API 文档与鉴权
- 腾讯云 SES 发信域名与模板
- 腾讯数智人 AppKey / AccessToken / 形象 ID
- LLM API Key

---

## 4. DEMO + B / Y

| 交付 | 用途 |
| --- | --- |
| DEMO | 全链路可演示：选品 / 自有商品 → 分析报告 → 获客 → 数字人邮件 → 流失召回 |
| B | B 站发布演示与获客内容 |
| Y | YouTube 发布演示与海外获客内容 |

---

## 5.

（待补）
