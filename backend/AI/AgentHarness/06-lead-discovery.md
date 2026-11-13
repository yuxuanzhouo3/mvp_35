# Harness 06 · 线索发现 / 富化 — Parallel Fan-out Flow

架构：按通道扇出 provider → 归一 `leads` → 规则 `lead-score` → LLM 可选补非评分字段。挂点：B1–B5 · enrichment · `lead-score`。

主扛：**QR ≥60%** · **LeadT ≤ 3 min** · 为北星 **AR** 供合格分子。

**不要**：ReAct 串行拖慢发现；模型改评分。

---

## 流水线（Harness 固定）

```text
1. fan_out    并行调用 providers（电商/社交/展会/代理/企查查…）
2. await      每路独立 timeout；超时跳过该路，不拖整批
3. normalize  归一为 leads 行（去重键：email/domain/external_id）
4. score      规则 lead-score（唯一评分真源）
5. enrich_llm 可选：公司摘要等非评分字段
6. emit       QR 分母=入库数；分子=score≥θ
```

```text
LeadT = discovery_success − start   ≤ 3 min
单路超时建议 ≤ 45–60s；整批硬顶 180s
```

---

## Fixture 形状

```json
{
  "case_id": "leads.fanout.qr.001",
  "channels": ["ecommerce", "enrichment"],
  "providers": {
    "ecommerce": {"latency_ms": 200, "rows": [{"email": "a@ex.com", "company": "Acme"}]},
    "enrichment": {"latency_ms": 5000, "timeout_ms": 1000, "rows": []}
  },
  "score_rules_version": "v1",
  "theta": 0.6,
  "expect": {
    "lead_t_ms_max": 180000,
    "slow_provider_skipped": true,
    "scores_from": "rules",
    "llm_cannot_set_score": true
  }
}
```

负面：串行假实现（Harness 检测 wall clock ≈ sum(latencies) 且无并行标记 → `fail`）。

---

## 超时与降级

| 项 | 值 |
| --- | --- |
| `budget_ms` | **整批 ≤ 180_000（LeadT）** |
| 单路 | `timeout_ms` 到 → `provider.skipped`，继续归一 |
| 全路失败 | `verdict=fail` 或空列表 + 可观测错误；不得假造高分线索 |
| `degrade` | 关 LLM enrich；scoring 仍跑 |
| DEMO | provider 可全 mock；契约与超时逻辑不变 |

---

## 断言表

| ID | 断言 | 失败即 |
| --- | --- | --- |
| L1 | 并行：存在重叠执行窗口或显式 `parallel=true` 事件 | `fail` |
| L2 | 超时路标记 skipped，不阻塞他路 | `fail` |
| L3 | 墙钟 ≤ LeadT 预算 | `fail` |
| L4 | `score` 仅来自规则；LLM 输出无 `score` 覆写 | `fail` |
| L5 | 归一去重后无双份同键 | `fail` |
| L6 | QR 计算口径：`score≥θ` ÷ 入库（供 Envaluate） | 口径错 → `fail` |

---

## Modes

| mode | 行为 |
| --- | --- |
| `live` | 真 provider（受合规）；记每路 latency |
| `replay` | 回放各路 rows + 超时事件 |
| `dry_run` | mock providers；可入库标记 `dry` |
| `degrade` | 跳过 enrich_llm；规则打分保留 |

---

## Trace 关键 stage

`fan_out.start` · `provider.call|timeout|ok` · `normalize` · `score` · `enrich_llm?` · `lead_t_check` · `qr.snapshot`
