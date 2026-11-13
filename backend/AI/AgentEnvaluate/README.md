# AgentEnvaluate · Agent 评测框架

对齐 [project.md](../../../project.md) **八率 + 五时效**，按 [AgentArchitect/parts-map.md](../AgentArchitect/parts-map.md) 六类 Agent **纵向分类**评测。

金额 / 评分 / 是否流失只由规则引擎；模型只解释与写文案；触达必须人工批准。RAAS（B9）卖结果抽成，**不污染普通 AR**。

---

## 三维评测

| 维 | 文档 | 问什么 | 过线怎么看 |
| --- | --- | --- | --- |
| **1. 商业核心 KPI** | [01-business-kpi.md](01-business-kpi.md) | 八率五时效 + **RAAS 对赌**（结果收费） | 租户中位数 / 对赌窗口验收 |
| **2. Agent 产品技术指标** | [02-tech-metrics.md](02-tech-metrics.md) | 正确性、时效、降级、人审门禁 | harness 批测 + 线上 P50 |
| **3. 其他 Agent 相关评测** | [03-other.md](03-other.md) | 安全、成本、合规、可观测 | 红线不可破；成本可降 |
| **4. Agent 架构图与选型** | [04-architecture.md](04-architecture.md) | 六类怎么连；相对 ReAct/辩论/全自动为何选它 | 对齐 Architect 原则 |

Harness（跑批 / 回放）落在 [`AgentHarness/`](../AgentHarness/README.md)；夹具侧图解：[harness-diagrams.md](harness-diagrams.md)。本目录定**指标口径、产品架构说明与验收表**。

---

## 纵向：六类 Agent → 主扛 KPI

| # | Agent（架构） | 评测卡 | 商业主扛 | 技术主扛 |
| --- | --- | --- | --- | --- |
| 1 | Chatbot · Grounded RAG | [by-agent/01-chatbot.md](by-agent/01-chatbot.md) | ActR · N% 可解释 | 数字锁定 · 降级 |
| 2 | 选品价利 · Fixed Flow | [by-agent/02-selection.md](by-agent/02-selection.md) | N% · AnaT · ActR | 检索词 · AnaT≤2min |
| 3 | 内容工厂 · Plan-Draft-Critique | [by-agent/03-content-factory.md](by-agent/03-content-factory.md) | OR · AR · ActR | 合规闸 · 可发布率 |
| 4 | Reachout · HITL Workflow | [by-agent/04-reachout.md](by-agent/04-reachout.md) | TR · OR · **AR** · AcqT | 人审门 · 红线 |
| 5 | Recall · Event Sequential | [by-agent/05-recall.md](by-agent/05-recall.md) | RecR · ActR_cold · ActT · RecT | 入队规则 · ≤24h |
| 6 | 线索发现 · Parallel Fan-out | [by-agent/06-lead-discovery.md](by-agent/06-lead-discovery.md) | QR · LeadT · AR | 并行超时 · 归一 |

---

## 商业北星与对赌关系（摘要）

```text
普通获客（B1–B8 漏斗）
  北星 AR = W ÷ D ≥ 8%     （exclude_from_ar 消息不进）
  配套：TR≥95% · OR≥40% · QR≥60% · AcqT≤3天

RAAS 对赌（B9 · 卖结果）
  约定窗口内交付「建立对话的有效客户数」≥ N
  未达标 → 甲方不付对赌款（或全额退）
  达标 → 按合同抽成 / 计件入账（验签 · 幂等）
  口径单列，不进普通 AR
```

完整定义与样例合同见 [01-business-kpi.md](01-business-kpi.md)。

---

## 读法

1. 产品 / 商务先看 **01**：八率五时效 + RAAS 对赌怎么验收收费。
2. 研发看 **02** + **by-agent/\***：每类 Agent 测什么、不过线怎么降级。
3. 安全 / 合规 / 成本看 **03**。
4. 产品架构图与选型见 [04-architecture.md](04-architecture.md)；源表 [AgentArchitect](../AgentArchitect/parts-map.md)；夹具图解 [harness-diagrams.md](harness-diagrams.md)。
