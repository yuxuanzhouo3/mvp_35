# AgentArchitect

| 文档 | 内容 |
| --- | --- |
| [parts-map.md](parts-map.md) | 六部件主选、备份表、一周调用链 |
| [catalog-backup-architectures.md](catalog-backup-architectures.md) | 现行 ≥20（A01–A24）备选库 + Pros/Cons |
| [catalog-100-by-popularity.md](catalog-100-by-popularity.md) | **业界 100 架构 · 按流行程度排序**（≠主选） |

## 六类架构图 + 选型对比

| # | 文件 | 选用架构 |
| --- | --- | --- |
| 1 | [01-chatbot.md](01-chatbot.md) | Grounded Conversational RAG |
| 2 | [02-selection.md](02-selection.md) | Fixed Flow + Tool-calling |
| 3 | [03-content-factory.md](03-content-factory.md) | Plan → Draft → Critique |
| 4 | [04-reachout.md](04-reachout.md) | HITL Workflow Agent |
| 5 | [05-recall.md](05-recall.md) | Event-triggered Sequential Agent |
| 6 | [06-lead-discovery.md](06-lead-discovery.md) | Parallel Fan-out Flow |

Harness → [`../AgentHarness/`](../AgentHarness/) · 评测 → [`../AgentEnvaluate/`](../AgentEnvaluate/)
