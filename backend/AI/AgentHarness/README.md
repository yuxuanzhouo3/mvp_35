# AgentHarness · 跑批 / 回放 / 超时 / 降级夹具

对齐 [AgentArchitect/parts-map.md](../AgentArchitect/parts-map.md) 六类架构；验收口径对齐 [AgentEnvaluate](../AgentEnvaluate/README.md)。

本目录定 **怎么跑、怎么夹、怎么断言**，不改规则公式，不开放通用 `POST /ai/agent`。

```text
AgentArchitect  → 选哪套架构
AgentHarness    → 用夹具按契约跑（本目录）
AgentEnvaluate  → 测什么过线
```

---

## 共享契约

### 一次运行 = Run

| 字段 | 含义 |
| --- | --- |
| `agent_id` | `chatbot` · `selection` · `content_factory` · `reachout` · `recall` · `lead_discovery` |
| `arch` | Architect 推荐架构名（不可随意换成开放 ReAct） |
| `mode` | `live` \| `replay` \| `dry_run` \| `degrade` |
| `case_id` | fixture / golden 用例 ID |
| `budget` | 墙钟超时（对齐五时效） |
| `trace` | 逐步事件；可回放 |
| `verdict` | `pass` \| `fail` \| `degraded` \| `blocked` |

### 四种 mode

| mode | 行为 |
| --- | --- |
| `live` | 真调模型 / provider；写 `ai_calls`；受超时与门禁 |
| `replay` | 用录制 `trace` + fixture，不发外网；断言结果稳定 |
| `dry_run` | 走完整流水线，**发送 / 发布工具恒关闭** |
| `degrade` | 强制无钥匙 / 超时 / provider 失败，断言落到规则模板 |

### 硬夹具（所有 Agent 共用）

| 夹具 | 规则 |
| --- | --- |
| **NumberLock** | 金额 / `N%` / 线索分 / 是否流失 **只读规则引擎**；模型输出不得覆写 |
| **HitlGate** | 触达类：`send` / `publish` 仅在 `approved` 后开放 |
| **BudgetClock** | 超过部件 `budget_ms` → 记失败或降级，禁止无界反思 |
| **RedlineBreaker** | bounce / complaint 超红线 → 限流，Agent 不得绕过 |
| **PromptPin** | 跑批钉死 `prompt_version` + `model`；回放比对同钉 |

### Trace 事件（最小集）

```text
run.start → stage.enter → tool.call | llm.call | rules.compute
         → gate.check → stage.exit → run.end(verdict)
```

触达类额外：`draft.ready` → `approval.pending` → `approval.granted|denied` → `send.attempt|blocked`。

---

## 六类 Harness 一览

| # | Agent | 架构 | Harness 文档 | 主预算 |
| --- | --- | --- | --- | --- |
| 1 | Chatbot | Grounded Conversational RAG | [01-chatbot.md](01-chatbot.md) | 对话延迟；数字锁定 |
| 2 | 选品价利 | Fixed Flow + Tool-calling | [02-selection.md](02-selection.md) | **AnaT ≤ 2 min** |
| 3 | 内容工厂 | Plan → Draft → Critique | [03-content-factory.md](03-content-factory.md) | 合规闸；可发布率 |
| 4 | Reachout | HITL Workflow | [04-reachout.md](04-reachout.md) | 人审门；TR 红线 |
| 5 | Recall | Event-triggered Sequential | [05-recall.md](05-recall.md) | **ActT / RecT ≤ 24 h** |
| 6 | 线索发现 | Parallel Fan-out | [06-lead-discovery.md](06-lead-discovery.md) | **LeadT ≤ 3 min** |

---

## 目录约定（落地时）

```text
AgentHarness/
  README.md                 # 本文件：共享契约
  01-…06-*.md               # 各架构 harness 设计
  fixtures/                 # 只读用例 JSON（可选）
  runners/                  # 实现时：按 agent_id 调度
  traces/                   # 录制回放（gitignore 大体量）
```

MVP 先定设计与断言表；`runners/` 可后补，夹具行为不得弱于本文。

---

## 与现有代码的挂点

| Agent | 现有入口 | Harness 包一层 |
| --- | --- | --- |
| Chatbot | `AI/support.support_reply` | 注入 `facts` fixture；断言 `numbers_locked` |
| 选品 | `AI/selection.refine_need` + 规则算数 | 固定四阶段 flow runner |
| 内容 / 触达 / 召回 / 线索 | 模块占位 / workers | 状态机或 fan-out runner + dry_run 发送 |

失败仍降级规则模板（已有 support / selection 模式）；关混元必须 `verdict=degraded` 且业务可用。
