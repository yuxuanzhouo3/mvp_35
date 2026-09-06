# PickGlobal

**Oversea Market Selling** · 选品分析与出海获客全链路闭环

跨境卖家从选品（或自有商品）到分析、获客、触达、流失召回的一条技术闭环。本仓库为 **MVP 35**。  
技术细节与成本见 [tech.md](tech.md)；分支流程见 [workflow.md](workflow.md)。

---

## 1. MVP 35

| 项 | 说明 |
| --- | --- |
| 项目 | MVP 35 |
| 产品名 | PickGlobal |
| 域名 | [pickgrobal.mornscience.top](https://pickgrobal.mornscience.top) |
| 定位 | Oversea Market Selling（海外市场销售） |
| 一句话 | 选品分析和出海获客全链路闭环 |
| 技术原则 | **仅用国内腾讯云 + 国内 AI**；对照 mvp_28/24/1 国内版 |

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

### 2.1 实现范围（已锁定）

| 项 | 决策 |
| --- | --- |
| 深度 | 生产级 |
| 目标市场（首版） | 美国 + 中国（税务规则）；基础设施全部国内 |
| 商品来源 | 手动 / CSV + **自定义国内 API**（不用 Amazon） |
| 获客来源 | **腾讯位置服务** + 自定义国内线索 API（不用 Google Places） |
| 触达 | **混元**文案 + **腾讯 SES**；数智人视频 **DEMO placeholder**（**不买 10h 包**） |
| AI | **仅腾讯混元**（可选通义作备份，默认不开） |
| DB | **云文档**（文档型）；MySQL 暂不上 |

### 2.2 链路实现要点

1. **商品入口**：录入、CSV、国内自定义 API → `products`
2. **分析报告**：利润、US/CN 税务、履约时间、风险 → `analysis_reports`（混元辅助摘要）
3. **跨境获客**：位置服务 / 自定义线索 → `leads`
4. **数字人邮件**：混元文案 → **数智人 placeholder**（正式 API 后接）→ SES → `outreach_messages`
5. **流失召回**：沉默规则 → `recall_jobs` → 再触达

---

## 3. 技术选型

| 方案 | 状态 | 覆盖范围 |
| --- | --- | --- |
| Vercel | 不采用 `[x]` | — |
| 腾讯云开发 CloudBase | 采用 `[✓]` | **Code + DB + 存储 + 函数** |

客户端：**cnwww**（Android / Mac / Windows / iOS）+ 微信小程序 + App Store。

### 3.1 数据库：MySQL vs 云文档

| | 云文档 | MySQL |
| --- | --- | --- |
| DEMO | **采用 `[✓]`** | 暂不上 |
| 原因 | 对齐 mvp_28；报告/触达是文档态；起步便宜 | 强 JOIN/对账以后再上 |
| PostgreSQL | 不用 | — |

详见 [tech.md](tech.md) §A2。

### 3.2 架构（国内）

```
客户端
  → CloudBase 云托管（Next.js）
  → 文档型 DB · 云存储 · 云函数
  → 混元 · 数智人 · SES · 位置服务
```

### 3.3 成本与规模方案（月）

| 档 | 用户 | 约计（无数智人视频包） |
| --- | --- | --- |
| DEMO | 内测 | **¥200–800** |
| S1 | **1 万** | **¥0.3万–1.2万** · 云文档 + 云托管 |
| S2 | **10 万** | **¥1.5万–5万** · 云文档 + MySQL + 队列 + Redis |
| S3 | **100 万** | **¥15万–50万+** · MySQL 主从分片 + 多服务 |

数智人 10h 包：**当前不买**（placeholder）。分项与升级条件见 [tech.md](tech.md) **Part C**。

### 3.4 交付顺序

| 阶段 | 交付 |
| --- | --- |
| A | Web 闭环 → 云托管 + `pickgrobal.mornscience.top` |
| B | 小程序 + Capacitor / Electron 壳 |
| C | SES 域名硬化、**再考虑**数智人正式包、监控限流 |

### 3.5 仓库结构（拟建）

```
mvp_35/
├── app/
├── components/
├── lib/cloudbase/          # 对齐 mvp_28 connector
├── clients/
├── cloudbase/Dockerfile
├── project.md
├── tech.md
└── workflow.md
```

---

## 4. DEMO + B / Y

| 交付 | 用途 |
| --- | --- |
| DEMO | 全链路演示（国内栈） |
| B | B 站 |
| Y | YouTube |

---

## 5.

（待补）
