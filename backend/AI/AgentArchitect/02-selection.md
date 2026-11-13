# 架构图 02 · 选品价利 — Fixed Flow + Tool-calling

挂点：`AI/selection.refine_need` · `selection-assist` · `pg-rules` · A1–A4  
主扛：**N%** · **AnaT≤2min** · **ActR**

---

## 架构图

```mermaid
flowchart LR
  Need[自然语言需求] --> Refine[LLM：提炼 query<br/>temperature 低]
  Refine --> Tools[Tools 并行<br/>货架/目录/报价]
  Tools --> Rules[规则引擎 pg-rules<br/>算 N/税/时效/风险]
  Rules --> Explain[LLM：只写解释<br/>不改金额]
  Explain --> Report[选品报告<br/>+ seed_analysis_id]

  subgraph 固定顺序 · 不可跳步
    Refine
    Tools
    Rules
    Explain
  end
```

```text
NL → refine_need → 货架工具 → calculate(rules) → 解释文案 → 报告
```

---

## 为什么选它

| 需求 | Fixed Flow 怎么满足 |
| --- | --- |
| AnaT≤2min | 步骤固定、可缓存、可并行货架；无反思死循环 |
| N% 可复算 | 金额只出规则；`rules_version` 快照 |
| 可测可回放 | Harness 逐步断言；失败点明确 |

## 和其他架构相比

| 备选 | 不选原因 |
| --- | --- |
| **自由 ReAct** | Thought→Act 可能绕过规则或反复搜，AnaT 与审计崩 |
| **Agentic RAG 改价** | 检索价若直接当利润，绕过 `pg-rules` |
| **Multi-agent 利润辩论** | 多模型争论售价 → 不可复算、贵、慢 |
| **Plan-Execute-Reflect** | 选品是确定性流水线，不需要动态重规划 |
| **纯 LLM 估利润** | 违反硬约束；看板八率失真 |

**一句话**：选品是「流水线算数」，不是「Agent 自由探索定价」。
