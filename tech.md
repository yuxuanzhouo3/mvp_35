# PickGlobal（MVP 35）技术栈

产品方案见 [project.md](project.md)。  
域名：`pickgrobal.mornscience.top`  
主路径：**腾讯云 CloudBase**（不用 Vercel）

---

# Part A · 腾讯云技术（本项目采用）

境外 Provider（Amazon、Google Places 等）见 project.md，此处不展开。

## A1. 总览

| 能力 | 腾讯产品 | 用途 |
| --- | --- | --- |
| 代码托管运行 | CloudBase **云托管**（CloudRun） | Next.js 15 SSR，`output: 'standalone'` |
| 业务数据库 | CloudBase **PostgreSQL** | 商品、报告、线索、触达、召回 |
| 对象存储 | **COS**（或 CloudBase 云存储对接 COS） | 报告附件、数智人视频 |
| 异步任务 | CloudBase **云函数 / 定时触发 / Jobs** | 拉品、分析、渲染、发信、召回调度 |
| 数字人视频 | **腾讯云智能数智人** | 个性化触达视频 |
| 邮件触达 | **腾讯云 SES** | `SendEmail` + 打开 / 退信回调 |
| 客户端（后期） | **微信小程序** + cnwww 多端壳 | 复用同一后端 API |
| 鉴权 SDK | `@cloudbase/js-sdk` / `@cloudbase/node-sdk` | 环境登录、服务端 DB/存储 |

```
Web / 小程序 / 原生壳
        ↓
CloudBase 云托管（Next.js standalone）
        ↓
PostgreSQL · COS · 云函数/Jobs
        ↓
数智人 API · SES ·（业务侧其它 Provider 另接）
```

应用层默认与兄弟 MVP 对齐：`Next.js + TypeScript + Tailwind + shadcn/ui`（见 Part B）。

## A2. CloudBase 云托管（Code）

| 项 | 约定 |
| --- | --- |
| 运行形态 | Docker 镜像 → 云托管服务 |
| 应用 | Next.js App Router，生产 `standalone` |
| 环境变量 | 全部挂在云托管，不进前端包 |
| 对照实现 | `mvp_1` / `mvp_24` / `mvp_28` |

| 变量 | 说明 |
| --- | --- |
| `WECHAT_CLOUDBASE_ID` / `NEXT_PUBLIC_WECHAT_CLOUDBASE_ID` | 环境 ID |
| `CLOUDBASE_SECRET_ID` | API 密钥 ID |
| `CLOUDBASE_SECRET_KEY` | API 密钥 |
| `DATABASE_URL`（或 CloudBase PG 连接串） | PostgreSQL |
| 域名 / HTTPS | 绑定 `pickgrobal.mornscience.top` |

SDK：浏览器 `@cloudbase/js-sdk`；服务端 `@cloudbase/node-sdk`（勿打进 Edge Runtime）。

```
cloudbase/
├── Dockerfile
└── migrations/
```

## A3. PostgreSQL（DB）

| 表 | 用途 |
| --- | --- |
| `products` | 选品 / 自有商品 |
| `product_sources` | 来源类型 |
| `analysis_reports` | 利润 / 税务 / 时间 / 风险 |
| `leads` | 线索 |
| `campaigns` | 活动 |
| `outreach_messages` | 邮件草稿与发送 |
| `digital_human_assets` | 数智人视频 / 形象任务 |
| `recall_jobs` | 流失召回 |
| `provider_credentials` | 外部密钥引用（加密） |
| `audit_logs` | 操作与发送审计 |

首版目标：**关系型 PG**（非国际版 Supabase）。

## A4. COS（文件）

| 存什么 | 说明 |
| --- | --- |
| 分析报告附件 | PDF / 导出包 |
| 数智人成片 | 渲染后写入 COS，邮件内嵌或附链 |
| 临时素材 | 形象、旁白音频等 |

密钥走腾讯云 CAM / COS env，仅云托管可见。

## A5. 云函数 / Jobs

| Job | 角色 |
| --- | --- |
| 商品拉取 / 分析 | 定时或队列 → 写 PG |
| 数智人渲染 | API → 轮询/回调 → COS → 更新 `digital_human_assets` |
| SES 发送 | 读 `outreach_messages` → `SendEmail` → 回写状态 |
| 流失召回 | 沉默规则 → `recall_jobs` → 再入发送队列 |
| SES 回调 | 打开 / 退信 / 投诉 → 更新触达与召回 |

可用云函数、云托管 worker 或定时触发器；要求可观测、可重试。

## A6. 智能数智人

| 项 | 说明 |
| --- | --- |
| 输入 | LLM 文案 + 形象 ID |
| 输出 | 视频 → COS |
| 密钥 | AppKey / AccessToken / 形象 ID |
| 状态 | `digital_human_assets`：queued / rendering / ready / failed |

## A7. SES（邮件）

| 项 | 说明 |
| --- | --- |
| API | `SendEmail` |
| 域名 | 发信域名验证、SPF/DKIM（Phase C） |
| 回调 | 打开、退信、投诉 |
| 原则 | 不走境外邮件 SaaS 作主路径 |

## A8. 微信与多端

| 阶段 | 交付 |
| --- | --- |
| A | Web → 云托管 + 自定义域名 |
| B | 微信小程序；Android / iOS / Mac / Win 壳（cnwww），后端仍 CloudBase |
| 可选 | CloudBase 微信登录（参考 mvp_28 国内版） |

## A9. 密钥清单（仅腾讯）

- CloudBase 环境 ID、`CLOUDBASE_SECRET_ID` / `CLOUDBASE_SECRET_KEY`
- PostgreSQL 连接串
- COS Bucket / Region / 密钥
- SES：发信域名、密钥、回调 URL
- 数智人：AppKey、AccessToken、形象 ID
- （Phase B）微信小程序 AppID / AppSecret

前端最多暴露 `NEXT_PUBLIC_*` 环境 ID。

## A10. 明确不用

- Vercel 主发布
- Supabase / Firebase 作国内主库
- 境外邮件主通道替代 SES
- 非腾讯对象存储作国内主存储

---

# Part B · 兄弟 MVP 技术盘点（选型对照）

扫描：`mvp_1` … `mvp_34`（2026-09-06）。空目录跳过：`12, 14, 16–18, 20, 31, 32`。

## B1. 共识栈

| 层 | 主流 | 备注 |
| --- | --- | --- |
| 框架 | Next.js App Router | 最常见 **15.2.x**（亦有 14 / 16） |
| 语言 | TypeScript | 几乎全覆盖 |
| UI | Tailwind + shadcn/ui | ~19 个有 `components.json` |
| 图表 / 校验 | Recharts / Zod | 模板常见 |
| 包管理 | pnpm 或 npm | 看 lockfile |

## B2. 后端 / 托管（与 Part A 相关）

| 能力 | 代表 |
| --- | --- |
| **CloudBase**（生产级对照） | mvp_1, mvp_24, mvp_28 |
| Docker | mvp_1, mvp_6, mvp_9, mvp_24, mvp_28 |
| Supabase（国际版常见，国内主库不用） | mvp_1, 5, 8, 24, 28, 33 |
| Vercel 配置（本项目不采用主路径） | mvp_1, 2, 9, 23, 24, 34 |

国内支付等横切：Alipay / 微信（mvp_8, 24, 28）；多端 `clients/`（mvp_9, mvp_24）。

## B3. 逐项目速览

| MVP | 主题 | 核心技术 |
| --- | --- | --- |
| 1 | PersonaLink | Next 14, CloudBase, Supabase, Firebase, Stripe, Docker |
| 2 | 娱乐/会员 | Next 14, Prisma, NextAuth, Stripe, PayPal |
| 3 | PriceCompare | Next 15, shadcn, Express |
| 4 | User Growth | Next 14, NextAuth, OpenAI, Stripe |
| 5 | MornGPT 内容 | Next 14, Supabase |
| 6 | Deepfake 前端 | CRA + MUI + ECharts（非 Next） |
| 7–15, 19, 21–23, 25, 29–30, 34 | 多为 shadcn 模板 | Next 14–16 |
| 8 | SiteHub | Next 14, Supabase, Stripe/Alipay/PayPal |
| 9 | SecureFiles | Next 15, Docker, **clients/** |
| 24 | 重业务 | Next 15, CloudBase, 支付/AI/Docker |
| 26 | mornGPT 多模块 | Python FastAPI |
| 27 | Frontend 模板 | Next 15 + React 19 |
| 28 | MornGPT | Next 15, **CloudBase 国内版** |
| 33 | Auth middleware | Next 16, Supabase, Tailwind v4 |
| 35 | **PickGlobal** | Part A（CloudBase PG/COS/Jobs） |

## B4. 架构模式

| 模式 | 说明 | 对本项目 |
| --- | --- | --- |
| A. 单体 Next | app + shadcn | UI 基线 |
| B. Next + CloudBase | standalone 云托管 | **采用**；读 mvp_28 / 24 / 1 |
| C. 前后端分离 | mvp_6 SPA；mvp_26 FastAPI | 不采用整仓 Python |
| D. 多端壳 | mvp_9 `clients/` | Phase B 参考 |

## B5. 可借鉴 / 勿照搬

| 需求 | 对照 | 拿走 |
| --- | --- | --- |
| CloudBase 部署 | mvp_28, 24, 1 | Dockerfile、env、standalone |
| Next 结构 | mvp_28 / 27 | app / components / lib |
| 多端 | mvp_9 | `clients/` 分层 |
| 邮件/数智人 | — | 以腾讯官方 SES / 数智人为准 |

勿照搬：Vercel 主发布、无业务空壳模板、mvp_26 整仓 Python 化。

## B6. Next 版本分布

| 大版本 | 约数 | 示例 |
| --- | --- | --- |
| 14.x | ~7 | 1, 2, 4, 5, 7, 8, 10 |
| 15.x | ~12 | 3, 9, 11, 13, 15, 21–22, 24–25, 27–30 |
| 16.x | ~4 | 19, 23, 33, 34 |

---

# 总结

- **采用（Part A）**：CloudBase 云托管 + PostgreSQL + COS + Jobs + 数智人 + SES +（后期）微信小程序。  
- **应用层**：Next 15 + TS + Tailwind + shadcn（兄弟项目共识）。  
- **代码对照**：`mvp_1` / `mvp_24` / `mvp_28`；多端看 `mvp_9`。
