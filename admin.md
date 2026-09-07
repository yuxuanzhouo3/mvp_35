# PickGlobal 平台管理后台设计

本文定义 PickGlobal 平台运营人员使用的 `/admin` 管理后台。它与企业客户工作台中的 `owner/admin` 权限不是同一套角色：企业管理员只能管理本企业，平台管理员可在授权范围内管理广告、平台用户、行为分析、用户邀请和用户召回。

方案参考兄弟项目的可复用设计：

- `mvp_28`：广告素材预览、位置筛选、优先级、上下架和 CloudBase 存储思路。
- `mvp_1`：独立后台导航、统计卡片、用户列表、设备/支付/AI 用量分析和细粒度管理员权限。
- `mvp_5` / `mvp_26`：运营看板、按日用量汇总，以及 overview / breakdown / trend / export 分层分析接口。
- `mvp_9` / `mvp_25`：邀请码、复制链接、邮件邀请、阶梯奖励和解锁进度体验。
- `mvp_30`：异步任务的 `status / progress / steps / error` 进度模型。
- `back.md`：CloudBase Auth、FastAPI、worker、云文档、审计、限流和迁移边界。

不直接复制兄弟项目的独立弱口令、硬编码管理员邮箱、默认密钥或国际数据源。PickGlobal 继续遵守“国内腾讯云 + CloudBase + FastAPI + 混元 + SES”的约束。

---

## 1. 产品目标

后台围绕一个平台增长闭环设计：

```text
平台广告曝光
  → 用户访问、注册和关键行为
  → 行为分群与流失识别
  → 邀请增长或召回触达
  → 回流、激活、付费
  → 效果归因并优化广告/策略
```

首版必须覆盖五个业务域：

1. **Ad 广告管理**：管理 PickGlobal 自有页面中的广告位、素材、投放规则和效果。
2. **用户数据管理**：搜索用户、查看统一画像、处理状态和隐私请求。
3. **行为分析**：事件、漏斗、留存、路径、分群和功能采用率。
4. **用户邀请**：邀请活动、邀请码、奖励规则、反作弊和转化归因。
5. **用户召回**：识别沉默/流失用户，创建召回活动并追踪回流。

这里的“用户召回”指 PickGlobal 平台注册用户的产品召回；`back.md` 中的 `recall_jobs` 指企业客户对海外线索的业务召回。两者必须使用不同的数据集合、API 和权限，避免混淆。

---

## 2. 设计原则

- **平台级与租户级隔离**：平台运营后台不复用企业工作台的 `tenant admin` 判断。
- **先观察、后操作**：普通运营角色默认只读；封禁、导出、发信、奖励调整等操作需要更高权限。
- **所有批量动作可预览**：先显示命中人数、排除人数、成本估算和样例，再允许发布。
- **高风险动作双重确认**：批量触达、封禁、删除、额度调整和广告发布记录操作原因。
- **规则决定对象，AI辅助内容**：分群、流失和奖励资格由确定性规则判断；混元只生成解释或文案草稿。
- **可归因**：广告、邀请、召回统一带 `campaign_id / source / medium / content`。
- **可撤销**：广告可下架、活动可暂停、未执行任务可取消；不以硬删除作为日常操作。
- **隐私最小化**：列表默认脱敏，查看完整邮箱/手机、导出或下载必须有权限和审计。
- **指标口径固定**：每个看板展示时区、时间范围、统计延迟、口径说明和数据更新时间。

---

## 3. 后台信息架构

桌面端使用固定左侧导航；移动端仅支持紧急查看和暂停活动，不把复杂配置压缩成完整移动编辑器。

```text
/admin
├── overview                 运营总览
├── ads                      广告管理
│   ├── placements           广告位
│   ├── creatives            素材库
│   ├── campaigns            投放活动
│   └── analytics            广告效果
├── users                    用户数据
│   ├── segments             用户分群
│   ├── privacy-requests     导出/删除请求
│   └── risk                 风险用户
├── analytics                行为分析
│   ├── events               事件趋势
│   ├── funnels              漏斗
│   ├── retention            留存
│   ├── paths                行为路径
│   └── features             功能采用
├── invitations              用户邀请
│   ├── campaigns            邀请活动
│   ├── codes                邀请码
│   ├── rewards              奖励账本
│   └── fraud                反作弊
├── recall                   用户召回
│   ├── audiences            待召回人群
│   ├── campaigns            召回活动
│   ├── templates            内容模板
│   └── suppression          禁止触达名单
├── jobs                     批处理任务
├── audit                    审计日志
└── settings                 权限、字典和全局配置
```

全局顶栏包含：

- 环境标识：`TEST` / `PRODUCTION`，生产环境使用醒目标识。
- 全局搜索：按用户 ID、脱敏邮箱、活动 ID、广告 ID、邀请码搜索。
- 时间范围和时区：默认最近 30 天、`Asia/Shanghai`。
- 数据新鲜度：实时、小时级或 T+1。
- 待处理中心：失败任务、投诉异常、待审批活动、隐私请求。
- 当前管理员、角色和退出入口。

---

## 4. 运营总览

首页不是所有统计的堆叠，而是“异常优先 + 增长闭环”的指挥台。

### 4.1 核心指标

- 用户：总用户、今日新增、激活用户、DAU/WAU/MAU。
- 转化：访问 → 注册 → 首次商品分析 → 首次线索 → 首次触达 → 付费。
- 留存：次日、7 日、30 日留存和近 30 日流失人数。
- 广告：曝光、点击、CTR、目标转化、广告贡献注册。
- 邀请：发起人数、接受人数、有效邀请、邀请注册转化率、奖励成本。
- 召回：目标人数、送达、回流、重新激活、付费恢复、投诉/退订。

### 4.2 首页布局

1. 第一行：新增用户、激活率、7 日留存、付费转化四张指标卡，带环比。
2. 第二行：全链路转化漏斗和 30 日新增/活跃趋势。
3. 第三行：广告、邀请、召回三张渠道效果卡，可跳转详情。
4. 第四行：运营待办和风险告警。
5. 底部：最近发布活动、失败任务和管理员操作。

告警示例：

- SES bounce/complaint 超过阈值。
- 广告 CTR 或目标转化突然下降。
- 同设备批量注册、邀请码自邀或奖励异常。
- 召回活动频率超限。
- 数据任务延迟或事件量突然下降。

---

## 5. Ad 广告管理

### 5.1 管理对象

广告模块采用四层模型：

```text
广告位 placement
  → 投放活动 ad_campaign
  → 素材 creative
  → 展示/点击/转化事件
```

**广告位**定义页面中的稳定位置，不把位置字符串散落在组件中。首版位置：

- 官网：`home_hero_secondary`、`home_mid_banner`、`pricing_banner`
- 登录后工作台：`dashboard_top`、`dashboard_sidebar`
- 报告页：`report_footer`
- AI 对话页：`copilot_sidebar`

不沿用兄弟项目中只按 `top/bottom/left/right` 命名的方式；PickGlobal 使用“页面 + 语义位置”，便于长期扩展。

### 5.2 广告活动字段

- 基础：名称、广告主/内部来源、目标、负责人、备注。
- 状态：`draft → pending_review → scheduled → active → paused → ended / rejected`。
- 素材：图片或视频、标题、替代文本、落地页 URL、UTM 参数。
- 投放：广告位、优先级、权重、开始/结束时间、每日频控。
- 定向：登录状态、套餐、语言、设备、渠道、新老用户和用户分群。
- 排除：付费去广告用户、员工、测试账号、禁止触达用户。
- 目标：点击、注册、首次分析、付费或自定义事件。
- 审批：提交人、审批人、审批意见、发布时间和回滚版本。

媒体文件进入 CloudBase 云存储/COS，数据库保存对象 key、哈希、尺寸、MIME、时长和审核状态，不长期保存临时 URL。

### 5.3 页面设计

广告列表支持：

- 按名称、ID、广告位、状态、负责人和日期搜索筛选。
- 素材缩略图与大图/视频预览。
- 显示投放时间、优先级、曝光、点击、CTR 和目标转化。
- 单个上下架、复制、编辑、查看版本和效果。
- 冲突提示：同广告位、同人群、同时间段的活动重叠。

创建流程采用四步向导：

1. 选择目标和广告位。
2. 上传素材并预览桌面/移动效果。
3. 设置时间、定向、频控和目标事件。
4. 展示预计覆盖人数、冲突、链接安全检查和最终确认。

### 5.4 新设计：可验证投放

- 支持活动保留 5%–10% 对照组，评估真实增量而非只看最后点击。
- 同一广告位按活动权重选择，不只依赖整数优先级。
- 服务端记录最终命中的规则版本，避免历史报表被后续配置改变。
- 点击先写内部归因事件，再使用允许域名列表执行跳转。
- 首版只做 PickGlobal 自有流量广告，不建设第三方程序化广告平台。

---

## 6. 用户数据管理

### 6.1 用户列表

默认列：

- 用户 ID、脱敏邮箱/手机、昵称。
- 注册时间、来源、地区/语言、最近活跃时间。
- 当前套餐、企业数量、生命周期阶段。
- 近 30 日关键行为数和风险标签。
- 状态：`active / limited / suspended / deletion_pending / deleted`。

筛选条件：

- 注册/活跃时间、渠道、设备、语言、套餐。
- 是否完成首次商品分析、客户发现、AI 触达。
- 是否由邀请进入、是否邀请过其他用户。
- 活跃/沉默/流失阶段、风险级别、召回状态。

支持保存为动态分群；大规模导出必须异步生成短期有效文件。

### 6.2 用户 360° 详情

用户详情使用标签页：

1. **概览**：账号、CloudBase 身份、生命周期、来源和标签。
2. **企业与权限**：所属 tenant、企业角色；平台管理员不可直接用此页越权读取企业业务正文。
3. **行为时间线**：按事件显示登录、模块使用、支付、邀请和召回互动。
4. **套餐与用量**：订阅、权益、额度和 usage ledger 摘要。
5. **邀请关系**：邀请人、被邀请人、奖励和异常。
6. **触达记录**：召回活动、送达、打开、点击、退订和投诉。
7. **安全与隐私**：登录设备摘要、风险信号、数据导出/删除请求。
8. **审计**：管理员对该用户执行的所有操作。

### 6.3 管理动作

- 添加/移除运营标签。
- 限制或恢复账号。
- 失效全部会话。
- 手动加入或排除分群。
- 调整额度：只能通过不可变调整账本，必须填写原因。
- 处理数据导出/删除请求。
- 加入 suppression list。

禁止直接编辑：

- 支付成功状态。
- 微信/SES webhook 原始结果。
- 已确认的用量账本记录。
- 用户密码或 CloudBase 身份凭证。

---

## 7. 行为分析

### 7.1 事件规范

前后端统一事件信封：

```json
{
  "event_id": "evt_xxx",
  "event_name": "product_analysis_completed",
  "occurred_at": "ISO-8601",
  "user_id": "usr_xxx",
  "anonymous_id": "anon_xxx",
  "tenant_id": "ten_xxx",
  "session_id": "ses_xxx",
  "properties": {},
  "context": {
    "platform": "web",
    "app_version": "1.0.0",
    "language": "zh-CN",
    "source": "invite",
    "campaign_id": "cmp_xxx"
  },
  "schema_version": 1
}
```

核心事件：

- 获取：`page_viewed`、`signup_started`、`signup_completed`
- 激活：`tenant_created`、`product_imported`、`product_analysis_completed`
- 核心价值：`lead_discovery_completed`、`campaign_created`、`outreach_sent`
- 收入：`checkout_started`、`payment_succeeded`、`subscription_expired`
- 邀请：`invite_created`、`invite_opened`、`invite_accepted`、`invite_reward_granted`
- 广告：`ad_impression`、`ad_clicked`、`ad_goal_completed`
- 召回：`recall_sent`、`recall_opened`、`recall_clicked`、`user_reactivated`

禁止在事件属性中写入完整邮件正文、联系人列表、令牌、密钥或不必要的个人信息。

### 7.2 分析能力

- **事件趋势**：次数、用户数、人均次数，按套餐/渠道/设备分解。
- **转化漏斗**：支持步骤顺序、转化窗口、按首次或任意完成计算。
- **留存分析**：注册或首次分析为起点，按日/周查看回访或关键事件留存。
- **行为路径**：查看某事件前后最常见的步骤，限制路径深度避免噪声。
- **功能采用**：商品分析、客户发现、AI 触达和召回的使用覆盖率。
- **用户分群**：属性条件 + 行为条件 + 时间窗口组合。

推荐默认漏斗：

```text
访问官网
  → 完成注册
  → 创建企业
  → 导入首个商品
  → 完成首份分析
  → 发现首批客户
  → 创建首次触达
  → 购买套餐
```

### 7.3 指标口径

- 激活用户：注册后 7 日内完成首份商品分析。
- 活跃用户：统计期内至少完成一个核心业务事件，而不是只访问页面。
- 沉默用户：连续 7 日无核心业务事件。
- 流失风险：连续 14 日无核心业务事件，且历史上至少完成过一次核心价值事件。
- 已流失：连续 30 日无核心业务事件。
- 召回成功：收到召回后 7 日内再次完成核心业务事件。

阈值存入版本化配置，不写死在前端；报表保存计算口径版本。

### 7.4 数据延迟

首版不引入重型数仓：

- 原始事件追加写入 `behavior_events`。
- 小时任务汇总到 `analytics_daily` 和 `funnel_snapshots`。
- 总览允许小时级延迟，并显示最后更新时间。
- 单用户时间线可查询近期原始事件。
- 数据量增加后再将原始事件归档 COS，并评估 ClickHouse/数据仓库，不阻塞 MVP。

---

## 8. 用户邀请

### 8.1 邀请类型

- **用户邀请用户**：现有用户邀请新用户注册 PickGlobal。
- **企业邀请成员**：`owner/admin` 邀请成员加入 tenant，沿用 `back.md` 的企业成员流程。
- **运营定向邀请**：运营向候选用户发放限定邀请码。

三类邀请共享基础追踪能力，但奖励规则和接受结果不同；企业成员邀请不能错误发放拉新奖励。

### 8.2 邀请流程

```text
创建邀请活动
  → 配置有效期、资格、奖励和预算
  → 生成不可预测邀请码/签名链接
  → 分享或定向发送
  → 访问并完成注册
  → 风险检查
  → 满足有效条件
  → 通过 reward ledger 发放奖励
```

“有效邀请”默认要求：

- 新用户首次注册，而非已有账号重新绑定。
- 完成邮箱/手机验证。
- 在有效期内完成首次商品分析。
- 未命中自邀、同设备批量注册或其他高风险规则。

### 8.3 活动配置

- 名称、活动类型、开始/结束时间、总预算。
- 邀请人资格：套餐、注册时长、账号状态。
- 被邀请人资格：新用户、地区、渠道。
- 邀请人奖励和被邀请人奖励。
- 奖励触发事件、延迟确认期、每人上限。
- 落地页、分享文案和归因窗口。
- 风险阈值和人工复核策略。

状态：

```text
draft → pending_review → scheduled → active → paused → ended
                                      └──────→ budget_exhausted
```

### 8.4 反作弊

- 禁止同一用户自邀。
- 检查账号、设备、IP 网段、支付主体和短时批量注册信号。
- 奖励先进入 `pending`，确认期后变为 `granted`。
- 风险奖励进入 `held`，由有权限的管理员审核。
- 已发奖励只能通过反向账本 `reversed` 撤销，不改写历史记录。
- 规则只输出风险等级和原因，不仅凭单一 IP 自动封禁。

### 8.5 邀请看板

- 邀请链接创建数、打开数、注册数、有效邀请数。
- 邀请漏斗和各步骤转化率。
- 邀请带来的激活、付费和 30 日留存。
- 单个有效邀请成本、奖励预算使用率。
- Top 邀请人和异常邀请网络。

活动详情同时提供类似 `mvp_9` / `mvp_25` 的阶梯奖励预览：

- 以 `1 / 3 / 5 / 10` 个有效邀请作为可配置的默认阶梯，而不是写死业务奖励。
- 每个阶梯显示目标人数、奖励内容、已解锁人数、待确认人数和预计成本。
- 支持复制邀请码、复制签名链接和发送邀请邮件；所有渠道归入同一个 invitation ID。
- 用户侧显示当前进度，后台侧显示各阶梯转化和奖励负债。

---

## 9. 用户召回

### 9.1 待召回人群

系统每日根据确定性规则计算生命周期阶段：

```text
new → activated → engaged → silent → at_risk → churned → reactivated
```

可配置召回场景：

- 注册后未完成首份分析。
- 完成分析但未发现客户。
- 曾使用核心功能，连续 14/30 日无活跃。
- 套餐即将到期或已经到期。
- 额度耗尽后未升级。
- 邀请已打开但未完成注册。

必须排除：

- 已退订、投诉、硬退信或 suppression 用户。
- 账号已封禁/删除、隐私删除处理中用户。
- 频率上限内已被触达的用户。
- 员工、测试账号和实验对照组。

### 9.2 召回活动流程

```text
选择场景或用户分群
  → 冻结目标人群快照
  → 应用排除与频控
  → 混元生成文案草稿
  → 人工审核
  → 发送测试
  → 排期发布
  → worker 分批调用 SES
  → 事件回流
  → 计算送达、回流和增量效果
```

活动状态：

```text
draft → audience_ready → pending_review → scheduled → sending
                                                   → paused
                                                   → completed
                                                   → failed
```

### 9.3 内容和频控

- 模板变量只能来自白名单，如昵称、套餐、最近使用模块。
- 不把企业客户名单、邮件正文或分析报告全文发送给混元。
- 每封邮件包含退订入口和活动追踪参数。
- 用户级、渠道级和平台级分别限频。
- 默认同一用户 7 日内最多一封营销召回；具体值可配置。
- bounce/complaint 达到阈值自动暂停活动并告警。
- 首版渠道只接腾讯云 SES；站内信、短信和微信通知作为后续 adapter。

### 9.4 新设计：增量召回

每个召回活动可保留随机对照组。效果页同时展示：

- 总回流率：收到召回后回流人数 / 成功送达人数。
- 自然回流率：对照组同期回流人数 / 对照组人数。
- 增量回流率：总回流率 - 自然回流率。
- 增量付费和每个增量激活成本。

这可避免把用户本来就会回来的行为全部归功于召回邮件。

---

## 10. 跨模块用户分群

广告、分析、邀请和召回共用 `segments`，但各活动发布时保存不可变快照。

分群条件示例：

```text
用户属性：
  plan = free
  language = zh-CN
  registered_at within 30 days

AND 行为：
  product_analysis_completed >= 1 in last 14 days
  outreach_sent = 0 in last 14 days

EXCLUDE：
  suppression = true
  risk_level = high
```

分群类型：

- 动态分群：查询时按最新条件计算。
- 快照分群：活动发布时冻结成员和规则版本。
- 手工分群：由授权管理员导入用户 ID；必须校验、去重和审计。

列表展示估算人数；真正发布前由 worker 重新计算、应用排除并生成快照，避免页面估算与实际发送不一致。

---

## 11. UI 与视觉规范

后台延续官网的国际 B2B SaaS 视觉，但更强调信息密度和操作安全：

- 浅色主题为主；深海军蓝文字、钴蓝主色、翠绿成功色。
- 卡片圆角 12–16px，边框清晰，阴影克制。
- 数据表格使用粘性表头、列设置、批量选择、游标分页和空状态。
- 图表使用 Recharts；颜色不能作为唯一状态表达。
- 状态统一使用 Badge，危险操作使用红色且与普通主按钮分离。
- 复杂创建流程使用步骤向导；编辑页保留未保存提示。
- 详情采用右侧 Drawer 快速查看，完整调查进入独立页面。
- 所有指标卡支持点击查看组成数据，避免“不可解释数字”。
- 桌面内容宽度充分利用，最小支持 1280px；移动端优先只读和暂停操作。
- 满足键盘操作、焦点可见、表单错误提示和 WCAG 对比度要求。

通用页面结构：

```text
标题 + 口径/说明                         主要操作
指标卡 / 风险提示
搜索 + 筛选 + 保存视图 + 导出
表格或图表
分页 / 数据更新时间
```

---

## 12. 平台管理员权限

平台角色与企业角色分开存储：

- `platform_super_admin`：平台角色和全局安全设置；人数最少。
- `platform_operator`：用户标签、广告和普通运营配置。
- `platform_analyst`：分析和脱敏用户数据只读。
- `platform_growth`：广告、邀请、召回活动；不能管理管理员。
- `platform_support`：用户详情、会话失效和工单相关操作。
- `platform_auditor`：审计、活动版本和账本只读。

权限按动作定义，而不是只按页面：

```text
ads.read / ads.write / ads.publish
users.read_masked / users.read_pii / users.suspend / users.export
analytics.read / analytics.define_metric
invitations.write / invitations.publish / rewards.adjust
recall.write / recall.approve / recall.send
audit.read
platform_roles.manage
```

规则：

- 前端隐藏按钮只是体验；FastAPI 每个管理接口必须重新鉴权。
- `platform_super_admin` 不能成为代码中的万能绕过条件，仍需记录具体权限。
- 发布者不能审批自己创建的高风险批量召回活动。
- 查看 PII、导出、批量发送、额度/奖励调整都写审计日志。
- 管理员会话应启用 MFA、短有效期和敏感操作近期认证。

---

## 13. 数据模型

新增平台级集合不强制使用 `tenant_id`；必须显式标记 `scope = platform`，防止误用普通 tenant repository。

### 13.1 管理员与审计

`platform_admin_roles`

- `user_id`、角色、权限、状态、生效/失效时间、授予人。

`platform_audit_logs`

- 管理员、动作、资源、原因、变更前后摘要、`request_id`、IP/设备摘要和时间。
- 追加写，不允许普通管理员更新或删除。

### 13.2 广告

`ad_placements`

- 语义位置 key、页面、支持尺寸/媒体、状态。

`ad_creatives`

- 素材对象 key、哈希、类型、尺寸、时长、替代文本和审核结果。

`ad_campaigns`

- 目标、广告位、素材、定向规则、权重、频控、预算、时间和状态。

`ad_events_daily`

- 按日期、活动、素材、广告位和分群汇总曝光、点击、目标转化。

### 13.3 行为和分群

`behavior_events`

- 标准事件信封；仅追加写，按月归档。

`analytics_daily`

- 日期、事件、用户数、次数及常用维度汇总。

`metric_definitions`

- 指标名称、查询规则、版本、负责人和生效时间。

`segments`

- 名称、条件 DSL、用途、预计人数、版本和状态。

`segment_snapshots`

- 分群版本、活动、生成时间、成员对象引用、命中/排除数量。

### 13.4 邀请

`invitation_campaigns`

- 资格、奖励规则、预算、时间、状态和归因设置。

`invitations`

- 邀请人、邀请码哈希、活动、过期时间、接受人和状态。

`invitation_events`

- 创建、打开、接受、资格确认等追加事件。

`reward_ledger`

- 用户、活动、数量、`pending/granted/held/reversed`、原因和幂等键。

`invitation_risk_reviews`

- 风险等级、命中规则、证据摘要、审核人和结论。

### 13.5 平台用户召回

`user_lifecycle_states`

- 用户、当前阶段、规则版本、关键日期和原因。

`user_recall_campaigns`

- 场景、分群快照、模板、频控、对照组、排期和状态。

`user_recall_messages`

- 用户、活动、模板版本、SES message ID、投递/互动状态。

`contact_suppressions`

- 用户/地址哈希、渠道、原因、来源和时间。

注意：不得用 `recall_jobs` 保存平台用户召回；该名称保留给租户业务中的海外线索召回。

### 13.6 关键索引

- 管理员：`user_id` 唯一，`status + expires_at`。
- 广告：`placement_id + status + starts_at + ends_at`。
- 行为事件：`user_id + occurred_at`、`event_name + occurred_at`、`campaign_id + occurred_at`。
- 分群快照：`segment_id + segment_version + created_at`。
- 邀请码：只保存哈希并唯一索引；`inviter_user_id + created_at`。
- 奖励：`idempotency_key` 唯一，`user_id + created_at`。
- 生命周期：`user_id` 唯一，`stage + updated_at`。
- 召回消息：`campaign_id + status`、`ses_message_id` 唯一。
- suppression：`channel + destination_hash` 唯一。
- 审计：`admin_user_id + created_at`、`resource_type + resource_id + created_at`。

---

## 14. API 设计

统一前缀：`/api/v1/admin`。

```text
# 总览
GET    /overview
GET    /alerts

# 广告
GET    /ad-placements
GET    /ads
POST   /ads
GET    /ads/{id}
PATCH  /ads/{id}
POST   /ads/{id}/submit
POST   /ads/{id}/approve
POST   /ads/{id}/publish
POST   /ads/{id}/pause
GET    /ads/{id}/analytics

# 用户与分群
GET    /users
GET    /users/{id}
POST   /users/{id}/suspend
POST   /users/{id}/restore
POST   /users/{id}/sessions/revoke
POST   /users/export
GET    /segments
POST   /segments
POST   /segments/{id}/estimate
POST   /segments/{id}/snapshot

# 行为分析
GET    /analytics/events
POST   /analytics/funnels/query
POST   /analytics/retention/query
POST   /analytics/paths/query
GET    /analytics/features

# 邀请
GET    /invitation-campaigns
POST   /invitation-campaigns
POST   /invitation-campaigns/{id}/approve
POST   /invitation-campaigns/{id}/publish
GET    /invitations
GET    /rewards
POST   /rewards/{id}/hold
POST   /rewards/{id}/grant
POST   /rewards/{id}/reverse

# 平台用户召回
GET    /user-recall/audiences
GET    /user-recall/campaigns
POST   /user-recall/campaigns
POST   /user-recall/campaigns/{id}/preview
POST   /user-recall/campaigns/{id}/send-test
POST   /user-recall/campaigns/{id}/approve
POST   /user-recall/campaigns/{id}/schedule
POST   /user-recall/campaigns/{id}/pause
GET    /user-recall/campaigns/{id}/analytics

# 运维
GET    /jobs
POST   /jobs/{id}/retry
GET    /audit-logs
GET    /privacy-requests
POST   /privacy-requests/{id}/complete
```

接口要求：

- 所有写接口接收 `Idempotency-Key`。
- 列表使用游标分页和字段白名单排序。
- 导出、分群快照、批量发信和大查询返回 `202 + job_id`。
- 批量活动发布前要求有效的 preview 版本；人群或模板变化后旧 preview 失效。
- 错误响应带 `request_id`，但不泄露 PII、内部查询或密钥。

---

## 15. 技术架构

首版不创建独立微服务，继续使用 `back.md` 的模块化 FastAPI 和独立 worker：

```text
Next.js /admin
  → /api/v1/admin/*
  → FastAPI admin routers
       ├── platform RBAC
       ├── admin domain services
       ├── platform repositories
       └── audit middleware
  → CloudBase 云文档 / 云存储

CloudBase 定时器
  → Python worker
       ├── 行为小时/日汇总
       ├── 生命周期计算
       ├── 分群快照
       ├── 邀请资格与奖励确认
       ├── 广告/召回归因
       └── SES 分批发送与回调处理
```

代码建议：

```text
backend/app/domains/platform_admin/
├── access/
├── ads/
├── users/
├── analytics/
├── segments/
├── invitations/
├── user_recall/
└── audit/

front/app/admin/
├── (dashboard)/
├── components/
└── login/
```

平台 repository 与租户 repository 分开，调用方必须显式选择，不能通过缺少 `tenant_id` 意外变成全表查询。

---

## 16. 安全、隐私与可靠性

- 管理入口使用 CloudBase Auth 身份 + 平台角色，不新建共享管理员密码。
- 生产后台建议限制可信网络或接入层，并开启 MFA。
- PII 默认部分遮罩，只有 `users.read_pii` 可临时查看。
- CSV 导出进入异步任务，文件加密存储、短期签名下载、到期自动删除。
- 广告落地链接只允许 `https`，执行域名允许列表和恶意链接检查。
- 素材上传限制 MIME、扩展名、大小、尺寸和视频时长，并扫描文件。
- SES webhook 先验签、去重再处理；发送任务具备暂停、限速和熔断。
- 邀请码使用加密安全随机值，数据库只保存哈希。
- 行为事件使用服务端事件 ID 去重；关键转化尽量由服务端确认。
- 审计日志不保存完整敏感值，只保存脱敏的变更摘要。
- 数据删除需同步处理用户画像、事件可识别字段、导出文件和缓存。
- 涉及营销邮件、个人信息、数据保留和跨境业务数据时，上线前完成法务确认。

高风险操作确认框必须展示：

- 将执行的动作。
- 预计影响用户数/活动数。
- 不可逆部分和回滚方式。
- 操作原因输入。
- 二次认证或审批状态。

---

## 17. 任务与状态可见性

所有长任务使用 `mvp_30` 的进度体验，但状态持久化：

```json
{
  "status": "running",
  "progress": 64,
  "steps": [
    {"name": "resolve_segment", "status": "completed"},
    {"name": "apply_suppression", "status": "completed"},
    {"name": "send_batches", "status": "running"}
  ],
  "error": null,
  "result_ref": null
}
```

后台任务中心显示：

- 类型、创建人、开始时间、耗时、进度。
- 输入摘要、影响数量和结果下载。
- 失败步骤、可重试性和 request/trace ID。
- 取消、重试和查看审计入口。

重试必须沿用原幂等范围，不能重复发放奖励或重复发送邮件。

---

## 18. 分阶段实施

### Phase 0：管理基础

- `/admin` 布局、CloudBase Auth、平台 RBAC、MFA 入口。
- 审计中间件、任务中心、生产环境标识。
- 运营总览使用基础用户/业务数据。

### Phase 1：用户数据管理

- 用户列表、筛选、360° 详情和脱敏。
- 状态管理、会话失效、隐私请求和安全导出。
- 动态标签和基础分群。

### Phase 2：广告管理

- 广告位、素材、活动、预览、审批和上下架。
- 曝光/点击/目标事件。
- 频控、分群定向和广告效果页。

### Phase 3：行为分析

- 事件 SDK/服务端埋点和事件字典。
- 日汇总、趋势、默认漏斗、留存和功能采用。
- 指标定义版本和数据新鲜度。

### Phase 4：用户邀请

- 邀请活动、邀请码、接受流程。
- 奖励账本、确认期、预算和基础反作弊。
- 邀请漏斗、留存和付费归因。

### Phase 5：用户召回

- 生命周期规则、待召回人群和 suppression。
- 模板、测试发送、审批、排期和暂停。
- SES 事件回流、频控和增量对照组。

### Phase 6：优化

- 路径分析、自定义漏斗和高级分群。
- 广告 A/B、邀请网络风险分析、召回自动旅程。
- 数据量达到真实瓶颈后再引入专用分析存储。

---

## 19. 首版验收标准

### 平台与权限

- 平台角色与企业 `owner/admin` 完全分离。
- 未授权用户不能访问 `/admin` 页面或 API。
- PII 查看、导出、发布、发送、奖励调整均可审计。

### 广告

- 可完成素材上传、桌面/移动预览、审批、排期、暂停和效果查看。
- 定向规则、频控、去广告权益和冲突检查生效。
- 曝光、点击和目标转化能按活动归因。

### 用户与行为

- 可按关键属性和行为筛选用户并查看 360° 详情。
- 注册到首次触达的默认漏斗可查询。
- 激活、沉默、流失和召回成功口径固定且可追溯版本。

### 邀请

- 邀请链接不可预测、可过期、可追踪且不能自邀。
- 奖励幂等，支持 `pending / granted / held / reversed`。
- 可查看邀请带来的激活、付费和留存。

### 召回

- 发送前能预览目标、排除、样例、频控和预计成本。
- 退订、投诉、硬退信和封禁用户不会被发送。
- 活动可暂停，失败可安全重试，不重复发送。
- 可比较实验组与对照组的增量回流效果。

---

## 20. 首版明确不做

- 不建设外部广告交易平台、竞价系统或第三方广告主自助平台开户。
- 不允许运营人员直接修改支付成功记录、不可变账本或 webhook 结果。
- 不允许 AI 自动决定封禁、奖励资格、流失状态或无人审核群发。
- 不为行为分析首版引入 Kafka、独立 ClickHouse 或复杂实时数仓。
- 不让浏览器持有 CloudBase 管理凭证、SES 密钥或全库访问能力。
- 不将平台用户召回与企业客户线索召回合并成同一业务模型。

最终后台应形成清晰闭环：**广告获取 → 用户行为 → 分群洞察 → 邀请增长/用户召回 → 增量归因 → 策略优化**。

---

## 21. 已实现的管理后台原型

管理界面已作为独立 Next.js 应用放在仓库根目录的 `admin/`，默认使用 `3001` 端口，避免与 `front/` 的 `3000` 端口冲突。

```text
admin/
├── app/
│   ├── components.tsx       # 响应式侧栏、顶栏、指标卡、表格和筛选组件
│   ├── globals.css          # 后台视觉系统与响应式规则
│   ├── layout.tsx           # Platform Admin 应用壳
│   ├── page.tsx             # 运营总览
│   ├── ads/page.tsx         # 广告管理
│   ├── users/page.tsx       # 用户数据
│   ├── analytics/page.tsx   # 行为分析
│   ├── invitations/page.tsx # 用户邀请
│   └── recall/page.tsx      # 用户召回
├── next.config.mjs
├── postcss.config.mjs
├── package.json
└── tsconfig.json
```

本地启动：

```bash
cd admin
pnpm install
pnpm dev
```

访问 `http://localhost:3001`。当前页面使用本地演示数据，已经实现响应式导航、搜索/状态筛选、指标卡、图表、漏斗、留存、阶梯奖励、生命周期和活动列表等交互外观。下一步接入时，将页面中的演示数组替换为本文件 §14 定义的 `/api/v1/admin/*` 接口；鉴权、发布、发送、封禁和导出等高风险按钮在服务端能力完成前不得视为生产可用。
