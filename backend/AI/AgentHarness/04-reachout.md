# Harness 04 · Reachout — HITL Workflow Agent

架构：状态机工作流；LLM 只生成 draft；发送必须人审。挂点：Campaign · `app/campaigns` / workers。

主扛：**TR ≥95%** · **OR** · 北星 **AR ≥8%** · **AcqT ≤3 天**。

硬约束：AI 生成 → 人工批准 → 发送。

---

## 状态机（Harness 强制）

```text
draft → pending_approval → approved → sending → delivered|bounced|failed
                 ↘ denied / expired
```

| 状态 | 允许的动作 |
| --- | --- |
| `draft` | LLM 写稿、改稿；**禁止 send** |
| `pending_approval` | 人审 UI / harness 注入批准；**禁止 send** |
| `approved` | 可调用 send（仍受 RedlineBreaker） |
| `sending` | 幂等投递；记 deliveries |
| `denied` | 终止；可回 draft |

Harness 在每步 `gate.check`：非法迁移 → `verdict=fail`。

---

## Fixture 形状

```json
{
  "case_id": "reachout.hitl-send.001",
  "audience": [{"lead_id": "L1", "email": "a@ex.com"}],
  "seed_analysis_id": "rpt_x",
  "draft_prompt": "short intro, no price rewrite",
  "approval": {"action": "grant", "by": "harness-user"},
  "redlines": {"bounce_rate": 0.0, "complaint_rate": 0.0},
  "expect": {
    "send_before_approval": "blocked",
    "send_after_approval": "allowed",
    "numbers_from_report_readonly": true
  }
}
```

负面用例：`approval.action=deny`、伪造 `approved` 跳过、bounce 超红线。

---

## 超时与降级

| 项 | 值 |
| --- | --- |
| draft 预算 | ≤ 45s / 封 |
| 人审等待 | harness 可注入即时批准；线上 AcqT 不计入写稿 |
| `degrade` | LLM 失败 → 模板草稿，仍进 `pending_approval` |
| `dry_run` | send 记录 `would_send`，不触达真实通道 |
| RedlineBreaker | bounce≥1.5% 或 complaint≥0.1% → 禁止再 send |

---

## 断言表

| ID | 断言 | 失败即 |
| --- | --- | --- |
| R1 | `draft` / `pending_approval` 调用 send → `blocked` | `fail` |
| R2 | 仅 `approved` 后 send 成功（dry_run 记 would_send） | `fail` |
| R3 | 状态不可跳过（draft→sending 非法） | `fail` |
| R4 | 红线触发后后续 send 全部 blocked | `fail` |
| R5 | 文案可含解释，不得改报告金额 | `fail` |
| R6 | deny 后不得 send | `fail` |

---

## Modes

| mode | 行为 |
| --- | --- |
| `live` | 真写稿；发送视环境（生产须真 HITL） |
| `replay` | 回放 draft 文本 + 批准事件序列 |
| `dry_run` | 完整状态机，发送 mock |
| `degrade` | 模板 draft + 仍要求批准 |

---

## Trace 关键 stage

`draft` · `approval.pending` · `approval.granted|denied` · `redline.check` · `send.attempt|blocked` · `delivery.*`
