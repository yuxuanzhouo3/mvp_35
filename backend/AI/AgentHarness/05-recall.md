# Harness 05 · Recall — Event-triggered Sequential Agent

架构：规则判定冷启/流失入队 → 固定触达序列 → 每步 LLM 写一封 → 批准后发。挂点：`app/recall` · `enqueue_recall` · activation/recall jobs。

主扛：**RecR** · **ActR_cold** · **ActT / RecT ≤ 24 h**。

**不要**：模型决定「是否流失」或改评分；入队只在规则。

---

## 流水线（Harness 固定）

```text
1. trigger     规则事件：cold_start | churn | …（fixture 注入规则结果）
2. enqueue     入队 recalls / activation_jobs（幂等：同 lead+trigger 不双入）
3. sequence    固定步：D0 → D3 → …（时钟可加速）
4. copy        每步 LLM 一封（可预生成）
5. approve     HitlGate（与 Reachout 同门禁）
6. deliver     首封 delivered 计 ActT / RecT
```

Harness 时钟：`virtual_clock` 可快进天数，但 **墙钟预算**仍断言「入队→首封」路径在模拟 24h SLA 内完成（预生成可 `copy_ahead=true`）。

---

## Fixture 形状

```json
{
  "case_id": "recall.cold-d0.001",
  "lead": {"id": "L9", "status": "lost", "score": 0.71},
  "rule_decision": {"enqueue": true, "trigger": "cold_start"},
  "sequence": ["D0", "D3"],
  "approval": {"action": "grant"},
  "copy_ahead": true,
  "expect": {
    "model_cannot_override_enqueue": true,
    "first_deliver_sla_h": 24,
    "score_unchanged": true
  }
}
```

负面：`rule_decision.enqueue=false` 但 prompt 要求「强制召回」→ 仍不入队。

---

## 超时与降级

| 项 | 值 |
| --- | --- |
| 入队→首封 | **≤ 24 h**（ActT / RecT）；P95>72h 告警口径留给 Envaluate |
| 单步文案 | ≤ 45s；失败用模板，不挡序列 |
| 预生成 | 允许在 D0 前写好 D0 文案，压缩 delivered 延迟 |
| `dry_run` | 不真实外发；记 sequence 进度 |
| 幂等 | 重复 trigger 不新建冲突 job |

---

## 断言表

| ID | 断言 | 失败即 |
| --- | --- | --- |
| K1 | `enqueue` 仅跟随 `rule_decision`，忽略模型自决 | `fail` |
| K2 | `lead.score` / 流失标记运行前后一致（规则外不变） | `fail` |
| K3 | 序列步顺序固定，不可由模型跳步乱序 | `fail` |
| K4 | 未批准不得 deliver | `fail` |
| K5 | `copy_ahead` 路径下首封 SLA 满足 expect | `fail` |
| K6 | 同 lead+trigger 二次 trigger → 幂等 | `fail` |

---

## Modes

| mode | 行为 |
| --- | --- |
| `live` | 真规则入队 + 真/ mock 发送 |
| `replay` | 回放入队事件 + 逐步文案 |
| `dry_run` | 虚拟时钟推进序列，发送 mock |
| `degrade` | 全文案模板；入队与批准逻辑不变 |

---

## Trace 关键 stage

`rule.trigger` · `enqueue` · `seq.D0|D3|…` · `copy` · `approval.*` · `deliver` · `sla.check`
