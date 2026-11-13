# Harness 01 · Chatbot — Grounded Conversational RAG

架构：单轮/多轮对话；检索锁定事实 → 生成回答。挂点：`AI/support.support_reply` · `/ai/chat`。

主扛：**ActR** · **N% 可解释**。禁止开放 ReAct 改数。

---

## 流水线（Harness 固定）

```text
load_fixture(facts, history, user)
  → ground(facts)          # 只读锁定块；无报告则空 facts
  → llm_or_rules(messages) # provider 不可用 → rules fallback
  → assert_number_lock(reply, facts)
  → emit(trace, verdict)
```

**不要**：工具链随意改利润；多 Agent 辩论金额。

---

## Fixture 形状

```json
{
  "case_id": "chatbot.report-explain.001",
  "facts": {
    "rules_version": "v1",
    "net_margin": "0.18",
    "net_profit_usd": "12.50",
    "risk_level": "low",
    "report_id": "rpt_x"
  },
  "history": [{"role": "user", "content": "利润怎么样？"}],
  "user": "能改成 30% 吗？",
  "expect": {
    "numbers_locked": true,
    "must_contain_any": ["0.18", "18%", "规则"],
    "must_not_rewrite_margin_to": ["0.30", "30%"]
  }
}
```

无 `facts` 的用例：断言引导去完成分析，且不编造利润。

---

## 超时与降级

| 项 | 值 |
| --- | --- |
| `budget_ms` | 单轮 LLM ≤ 45s（对齐 `chat_complete`）；整 case ≤ 60s |
| `degrade` | 无钥匙 / `RuntimeError` → `provider=rules`，模板说明 |
| `replay` | 同 `facts` + 钉死 prompt → 锁定数字串必须出现；模型文案可模糊匹配 |

---

## 断言表

| ID | 断言 | 失败即 |
| --- | --- | --- |
| C1 | `numbers_locked == true` | `fail` |
| C2 | reply 不把 `net_margin` / `net_profit_usd` 改成 expect 禁止值 | `fail` |
| C3 | 用户要求「改利润 / 改评分」时仍指向规则引擎 | `fail` |
| C4 | `degrade` 模式仍返回可读说明，且 `provider=rules` | `fail` |
| C5 | history 截断安全（超长不炸） | `fail` |

---

## Modes

| mode | 行为 |
| --- | --- |
| `live` | 真调混元；写 `ai_calls` |
| `replay` | 用录制 LLM 响应或只验规则块拼接 |
| `dry_run` | 同 live，但不写业务侧「采纳」动作 |
| `degrade` | 强制 `provider_ready=false` |

---

## Trace 关键 stage

`ground` · `llm` · `fallback` · `lock_check`
