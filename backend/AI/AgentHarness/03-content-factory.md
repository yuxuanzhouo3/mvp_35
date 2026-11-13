# Harness 03 · 内容工厂 — Plan → Draft → Critique

架构：Planner → Writer → Critic（合规 / 品牌 / 退订）→ 人工或开关发布。挂点：B7 · `/content/*`（占位可 mock）。

主扛：**OR** · **AR** · **ActR**。不进账本、不直接改线索分。

---

## 流水线（Harness 固定）

```text
1. plan     选题 / 渠道 / 受众 / 禁用词表
2. draft    Writer 出稿（可选：数字人占位挂在此后）
3. critique Critic：合规 · 品牌 · 退订 · 虚假承诺
4. gate     pass → pending_publish；fail → revise 或 blocked
5. publish  仅开关或人工批准后开放（HitlGate）
```

修订环：`critique.fail` → 最多 `max_revisions`（默认 2）→ 仍失败则 `blocked`，落入模板库降级。

---

## Fixture 形状

```json
{
  "case_id": "content.email-or.001",
  "brief": {
    "channel": "email",
    "product_seed": "rpt_x",
    "locale": "en-US",
    "forbidden": ["保证暴利", "无风险"]
  },
  "mock_plan": {"angle": "margin-transparency", "cta": "book-demo"},
  "expect": {
    "has_unsubscribe_hint": true,
    "no_forbidden_claims": true,
    "publish_requires_approval": true,
    "score_fields_untouched": true
  }
}
```

---

## 超时与降级

| 项 | 值 |
| --- | --- |
| `budget_ms` | 单篇 ≤ 90s；含 2 次修订 ≤ 180s |
| `degrade` | LLM 失败 → 模板库草稿；仍过 Critic 闸 |
| 数字人 | DEMO 占位；失败跳过，不影响文案 verdict |
| `dry_run` | 永远不调用真实发布 / 外发 |

---

## 断言表

| ID | 断言 | 失败即 |
| --- | --- | --- |
| F1 | 未 `approved` / 开关关 → `publish` 被 HitlGate 挡住 | `fail` |
| F2 | Critic 命中禁用承诺 → 不得 `pending_publish` | `fail` |
| F3 | 退订 / 合规提示按渠道要求出现（邮件类） | `fail` |
| F4 | 不写 `lead.score` / 利润字段 | `fail` |
| F5 | 超 `max_revisions` → `verdict=blocked` 或模板 `degraded` | `fail` if 仍强发 |
| F6 | 角色顺序 plan→draft→critique，不可跳过 critique | `fail` |

---

## Modes

| mode | 行为 |
| --- | --- |
| `live` | 真 LLM 三角色（可用同一模型不同 system） |
| `replay` | 钉死 plan/draft/critique 三段响应 |
| `dry_run` | 产出草稿 artifact，发布工具关闭 |
| `degrade` | Writer 用模板；Critic 仍跑规则词表 |

---

## Trace 关键 stage

`plan` · `draft` · `critique` · `revise` · `gate` · `publish_blocked|publish_allowed`
