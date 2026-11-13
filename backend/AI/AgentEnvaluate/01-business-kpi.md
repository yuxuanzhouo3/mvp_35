# 01 · 商业核心 KPI（八率 + 五时效 + RAAS 对赌）

来源：[project.md](../../../project.md) §2；实现口径：[algorithm.md](../../../algorithm.md) KPI · `snapshot`。

默认滚动 **30 天**。分母为 0 → `—`。对外用租户**中位数**。金额只认规则引擎。

---

## 1. 八率（产品经营看板）

| # | 指标 | 代号 | 公式 | S2 目标 | 商业含义 |
| --- | --- | --- | --- | --- | --- |
| 1 | 利润率 | `N%` | `N/R`；看板 `median(net_margin)` | 可复算；推荐 ≥15%；偏差 ≤5pt | 选品值不值做 |
| 2 | 行动率 | `ActR` | 一键获客/采纳 ÷ 完成报告 | ≥50% | 报告能否推动行动 |
| 3 | 触达率 | `TR` | delivered 人数 D ÷ 计划受众 A | ≥95% | 触达管道是否通 |
| 4 | 打开率 | `OR` | unique 打开 ÷ D | ≥40%（辅助） | 文案/标题是否打开 |
| 5 | **获客率** | `AR` | 有效获客 W ÷ D | **≥8%（北星）** | 触达后是否建联/成交 |
| 6 | 线索合格率 | `QR` | `score≥θ` ÷ 入库 | ≥60% | 线索池是否干净 |
| 7 | 冷客激活率 | `ActR_cold` | 序列内 open∨reply ÷ 入队 | ≥25% | 冷启是否唤醒 |
| 8 | 召回成功率 | `RecR` | 回暖 ÷ 召回触达 | ≥10% | 流失是否拉回 |

```text
A = approve 受众 − suppressed / bounced / 无邮箱
D = A 中至少 1 封 delivered
W = 触达后 14 天内 replied 或赢单 / 约见
```

红线（按封）：送达 ≥95%；bounce &lt;1.5%；complaint &lt;0.1%。  
`exclude_from_ar`（含 **RAAS / `channel=raas`**）**不进** 普通 AR 的分子分母。

---

## 2. 五时效（P50；超时记失败）

| # | 指标 | 代号 | 公式 | S2 |
| --- | --- | --- | --- | --- |
| 1 | 分析时效 | `AnaT` | 完成 − 请求 | ≤2 min |
| 2 | 线索时效 | `LeadT` | discovery 成功 − 发起 | ≤3 min |
| 3 | 获客时效 | `AcqT` | first_W − first_delivered（仅 W） | ≤3 天 |
| 4 | 激活时效 | `ActT` | 首封 delivered − 入队 | ≤24 h |
| 5 | 召回时效 | `RecT` | 首封 delivered − 触发 | ≤24 h |

告警：`ActT` / `RecT` 的 P95 &gt; 72h。

---

## 3. RAAS 对赌（结果收费 · B9）

### 3.1 定位

| 项 | 普通获客漏斗（B1–B8） | RAAS 对赌（B9） |
| --- | --- | --- |
| 卖什么 | SaaS 订阅 / 通道能力 | **结果**：帮甲方拿到可对话客户 |
| 收费条件 | 套餐 / 用量 | **达标才付**；未达标不付或退 |
| KPI 入口 | 北星 `AR` 等八率五时效 | **对赌交付量**（单列 ledger） |
| 是否进 AR | 是（获客目的消息） | **否**（`exclude_from_ar=true`） |
| 入账 | 订阅验签 | 对赌结算 / 成功抽成 · 幂等 · 验签 |

类比：*「1 周内帮助甲方商户获取 N 个客户并建立对话；获取不到不需要付钱。」*

### 3.2 对赌合同字段（评测 / 结算共用）

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `tenant_id` / `merchant_id` | 甲方商户 | T-10086 |
| `window_start` / `window_end` | 对赌窗口 | 签约日起 7×24h |
| `target_n` | 承诺交付人数 N | 20 |
| `success_event` | 什么叫「建立对话」 | `replied` 或 `meeting_booked`（与 W 同源语义，可收紧） |
| `channel_scope` | 允许通道 | email / 指定 B1–B5 |
| `seed_analysis_id` | 可选：绑定选品报告 | 报告 UUID |
| `fee_cents` | 达标应付（整数分） | 500000（¥5000） |
| `fee_mode` | `all_or_nothing` / `per_head` / `tiered` | all_or_nothing |
| `exclude_from_ar` | 固定 true | true |
| `idempotency_key` | 结算幂等键 | `raas-bet-{id}-{window}` |

### 3.3 验收公式

```text
DeliveredDialogs = 窗口内、channel_scope 内、success_event 成立、且归属该对赌单的去重人数
Pass            = DeliveredDialogs ≥ target_n
Payable         = Pass ? fee_cents : 0     （all_or_nothing）
                或 min(DeliveredDialogs, target_n) × unit_cents  （per_head）
```

**评测通过条件（商业）：**

1. 窗口结束可算出 `DeliveredDialogs`（无双重计数）。
2. `Pass=false` 时账本**无**对赌应付或已冲正；甲方侧展示「未达标 · 无需付费」。
3. `Pass=true` 时仅验签 / 确认后入 `raas_commission`（或对赌科目），幂等不双发。
4. 对赌触达消息全程 `exclude_from_ar`，普通看板 AR 不变。

### 3.4 对赌与八率五时效的关系

| 经营看板 | 对赌单 |
| --- | --- |
| 衡量平台 / 租户长期经营质量 | 衡量**单次结果交付**是否可收费 |
| AR ≥8% 是产品北星 | `DeliveredDialogs ≥ N` 是合同北星 |
| AcqT ≤3 天支撑「够快建联」 | 窗口常取 **7 天**（可配置），超时未满 N 即失败 |
| TR / QR / OR 是对赌**前置健康度** | 前置不达标应拒签或下调 N，而非硬冲对赌 |

**签约前闸门（建议）：** 近 30 天租户（或同类样本）`QR≥60%`、`TR≥95%`、红线未 trip，才开放对赌档；否则只卖订阅。

### 3.5 样例

| 场景 | 约定 | 结果 | 收费 |
| --- | --- | --- | --- |
| A 商户 · 水杯 · 中美 | 7 天内 15 个有效回复对话 | 18 | 付全额 |
| B 商户 · 冷启动弱 | 7 天内 15 个 | 6 | **不付** |
| C · 计件 | 每建联 1 人 ¥80，上限 30 | 22 | 付 22×80 |

---

## 4. 商业验收总表（S2）

| 功能 | 必看 | 过线信号 |
| --- | --- | --- |
| A3 | `N%` · `AnaT` | 关模型仍有 metrics；P50 ≤2 min |
| A4 | `ActR` | ≥50%；带 `seed_analysis_id` |
| B1–B5 | `QR` · `LeadT` · `AR` | QR≥60%；LeadT≤3 min；AR≥8% |
| B 触达 | `TR` · `OR` · 红线 | TR≥95%；bounce/complaint 红线 |
| B 冷启/召回 | `ActR_cold` · `RecR` · `ActT` · `RecT` | 率达标；P50 ≤24 h |
| B9 RAAS 对赌 | `DeliveredDialogs` · 账本 | 未达标 0 应付；达标幂等入账；不污染 AR |

看板：`GET /kpi/dashboard` 管八率五时效；对赌验收走 RAAS / 对赌结算接口与 ledger，**不混进 AR 卡片**。
