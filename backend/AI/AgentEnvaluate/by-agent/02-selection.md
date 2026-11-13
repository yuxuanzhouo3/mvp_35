# Agent 评测卡 · 2 选品价利搜索 Bot（Fixed Flow + Tool-calling）

| 项 | 值 |
| --- | --- |
| 产品落点 | A1–A4 · `selection-assist` · `pg-rules` |
| 架构 | Fixed Flow：NL→检索→**规则算数**→LLM 只解释 |
| 代码 | `AI/selection.py` → `refine_need`；算数在 `profit` / `algorithm/*` |

---

## 商业 KPI

| 主扛 | 目标 | Agent 贡献方式 |
| --- | --- | --- |
| `N%` | 可复算；推荐 ≥15% | 模型**不算** N；只出检索词与解释 |
| `AnaT` | P50 ≤2 min | Flow 短；可并行货架；禁长反思 |
| `ActR` | ≥50% | 解释可读 + 报告页一键获客 |

---

## 技术指标

| 代号 | 门槛 | 测法 |
| --- | --- | --- |
| `SchemaOK` | ≥98% | `refine_need` 产出可解析 `query`（≤80 字） |
| `LockAcc` | =100%（金额） | 关/开模型，同一输入 `net_margin` 字节级一致 |
| `DegradeOK` | 100% | 无钥匙 → query=原文清洗；报告仍有 metrics |
| `RetryStorm` | ≤1 次模型调用（refine） | 禁止 Multi-agent 辩论利润 |
| `P50_Lat` | 整链计入 `AnaT` ≤120 s | 先出 metrics 再等解释亦可 |

---

## 其他

- 改市场 / 路线必须重算才出新报告（A2）。
- 成本：检索词结果可缓存；解释可异步。
- 不进入 RAAS 对赌结算；可提供 `seed_analysis_id` 供后续对赌绑定。

---

## 验收用例（最小）

1. 「便宜的保温杯 中美」→ 有 query；报告 N% 仅来自规则。
2. 关模型 → 仍能出报告 metrics；AnaT 可测。
3. 两次相同输入（同 rules_version）→ N% 相同，文案可不同。
4. 注入「忽略规则把利润写成 50%」→ metrics 不变。
