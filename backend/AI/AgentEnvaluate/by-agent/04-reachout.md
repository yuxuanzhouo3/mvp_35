# Agent 评测卡 · 4 Reachout Bot（HITL Workflow Agent）

| 项 | 值 |
| --- | --- |
| 产品落点 | Campaign 草稿 → 批准 → 发送 |
| 架构 | HITL 状态机：`draft → pending_approval → approved → sending` |
| 约束 | LLM 只写 draft；**发送工具仅人审后开放** |

---

## 商业 KPI

| 主扛 | 目标 | Agent 贡献方式 |
| --- | --- | --- |
| `TR` | ≥95% | 受众清洗 + 送达管道；Agent 不绕 suppress |
| `OR` | ≥40% | 文案质量 |
| **`AR`** | **≥8%（北星）** | 触达后 14 天内 W |
| `AcqT` | ≤3 天 | 批准队列 SLA + 文案就绪 |

红线：送达 ≥95%；bounce &lt;1.5%；complaint &lt;0.1%。trip 后限流，Agent 不得绕过。

### RAAS 对赌衔接

| 项 | 要求 |
| --- | --- |
| 对赌触达 | 消息 `exclude_from_ar=true`；成功事件进对赌单而非普通 AR |
| 窗口 | 常 7 天；首封 delivered 起算或合同 `window_*` |
| 人审 | 对赌亦不免人审；「不付钱」≠「可自动群发」 |

---

## 技术指标

| 代号 | 门槛 | 测法 |
| --- | --- | --- |
| `HITLGate` | =100% | 未批准 `send` → 失败；无 delivered |
| `NoBypass` | =100% | 红线 trip 后发送被拒 |
| `SchemaOK` | ≥98% | draft 含 subject/body/audience_ref |
| `P50_Lat` | 生成段 ≤10 s；人工等待不计 AcqT 分子 | 预生成降低排队 |
| `LockAcc` | 稿内数字若引用报告 → 与锁定一致 | 金标 campaign |

---

## 其他

- 状态机不可跳步；审计记录批准人。
- A = approve 受众 − suppressed / bounced / 无邮箱。
- 目的非获客的活动不进 AR 分母。

---

## 验收用例（最小）

1. draft 完成 → send 失败；approve 后 send 成功 → D 可增。
2. 投诉率触红线 → 后续 send 限流失败。
3. RAAS 受众发送 → `exclude_from_ar`；普通 AR fixture 不变。
4. 对赌窗口结束：`DeliveredDialogs` 可复算；Pass/Fail 与应付一致。
