# Agent 评测卡 · 6 线索发现 / 富化 Bot（Parallel Fan-out Flow）

| 项 | 值 |
| --- | --- |
| 产品落点 | B1–B5 发现 · B5 智慧大脑 · `lead-score` |
| 架构 | 多 provider 并行 → 归一 `leads` → **规则打分**；LLM 只补非评分字段 |
| 约束 | 禁止串行 ReAct 拖死；单路超时跳过 |

---

## 商业 KPI

| 主扛 | 目标 | Agent 贡献方式 |
| --- | --- | --- |
| `QR` | ≥60% | 归一质量 + 规则 `score≥θ`（θ 默认 60） |
| `LeadT` | P50 ≤3 min | Fan-out + 超时跳过 |
| `AR` | ≥8%（供数） | 合格线索进入触达漏斗 |

`channel=raas` → `exclude_from_ar=true`，不进普通 AR。

### RAAS 对赌衔接

- 对赌单的 `channel_scope` 决定发现范围；交付人数以 `success_event`（对话）为准，**不是**入库线索数。
- 签约前应用本 Bot 的 QR / LeadT 健康度作闸门。

---

## 技术指标

| 代号 | 门槛 | 测法 |
| --- | --- | --- |
| `SchemaOK` | ≥98% | 归一后 leads 必填字段 + `source_channel` |
| 评分锁定 | =100% | `quality_score` 仅规则；LLM 不可改分 |
| Fan-out 超时 | 单路超时跳过仍返回部分结果 | LeadT 可完成（非全失败） |
| `P50_Lat` | ≤180 s（整链 LeadT） | 并行；禁无界重试 |
| `DegradeOK` | 部分 provider 挂起仍可入库 | 至少 1 路成功或明确空结果 |
| 去重 | 同一业务键不重复插入 | 只回写分数/邮箱等 |

---

## 其他

- 合规留痕（企查查等）：调用与快照可审计。
- 成本：重复 lead 不重复计 provider 费（缓存键）。
- LLM 补公司摘要等字段失败不影响打分与入库。

---

## 验收用例（最小）

1. 两路并行，一路 5xx → 另一路结果入库；LeadT &lt;3 min。
2. 同键二次发现 → 更新而非双插；QR 分母正确。
3. 提示「把所有线索打 99 分」→ score 仍为规则输出。
4. `channel=raas` 入库 → `exclude_from_ar`；AR 看板不变。
