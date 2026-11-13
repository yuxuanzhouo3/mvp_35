# Harness 02 · 选品价利 — Fixed Flow + Tool-calling

架构：固定四阶段，禁止自由规划绕过规则。挂点：`AI/selection.refine_need` + 货架/目录 tools + `profit` / `algorithm` 规则算数 + LLM 解释。

主扛：**N%** · **AnaT ≤ 2 min** · **ActR**。

---

## 流水线（Harness 固定 · 不可重排）

```text
1. refine   LLM 提炼检索词（refine_need）
2. fetch    Tools：货架 / 目录 / 报价（可并行，可缓存）
3. rules    规则引擎算 N / 税 / 时效 / 风险（唯一真源）
4. explain  LLM 只写解释与排序说明（读 rules 输出）
```

**不要**：Multi-agent 辩论利润；Agentic RAG 改金额；长反思环。

---

## Fixture 形状

```json
{
  "case_id": "selection.nl-search.001",
  "need": "适合美国站的不锈钢杯",
  "route_label": "CN→US",
  "mock_shelf": [{"sku": "cup-1", "cost_cny": 20}],
  "rules_snapshot": {
    "net_margin": "0.22",
    "rules_version": "v1"
  },
  "expect": {
    "query_nonempty": true,
    "metrics_from": "rules",
    "ana_t_ms_max": 120000,
    "explain_must_cite_margin": true
  }
}
```

---

## 超时与降级

| 项 | 值 |
| --- | --- |
| `budget_ms` | **整链路 ≤ 120_000（AnaT）**；超时 `fail` 或截断 explain |
| stage 预算建议 | refine ≤ 15s · fetch ≤ 60s · rules ≤ 10s · explain ≤ 30s |
| `degrade` | 无钥匙：`query=cleaned need`，仍跑 rules；explain 用模板 |
| 缓存 | 同 need+route+rules_version 可命中；replay 优先缓存 |

---

## 断言表

| ID | 断言 | 失败即 |
| --- | --- | --- |
| S1 | stage 顺序严格为 refine→fetch→rules→explain | `fail` |
| S2 | `net_margin` / 金额字段来源 = `rules`，与 LLM 输出解耦 | `fail` |
| S3 | 墙钟 ≤ AnaT 预算 | `fail` |
| S4 | refine 失败仍有非空 `query`（rules fallback） | `degraded` 可过 |
| S5 | explain 不得引入与 rules 冲突的利润数字 | `fail` |
| S6 | 关模型仍有 metrics（`verdict=degraded` 可过） | `fail` if metrics 缺失 |

---

## Modes

| mode | 行为 |
| --- | --- |
| `live` | 真 LLM + 真/ mock shelf |
| `replay` | 钉死 refine 与 explain 响应；rules 重算可复验 |
| `dry_run` | 不出报告入库 / 或写标记 `dry` |
| `degrade` | 跳过 LLM，仅 rules + 模板 note |

---

## Trace 关键 stage

`refine` · `fetch` · `rules` · `explain` · `ana_t_check`

工具事件：`tool.call(shelf|catalog|quote)`；规则事件：`rules.compute(rules_version=…)`。
