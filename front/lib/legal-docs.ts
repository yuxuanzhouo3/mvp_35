export const LEGAL_VERSION = '2026-10-04'

export const docIds = ['rules', 'privacy'] as const

export type DocId = (typeof docIds)[number]

export function isDocId(value: string): value is DocId {
  return (docIds as readonly string[]).includes(value)
}

const mergedIntoRules = new Set(['cio', 'terms', 'billing', 'service', 'dpa', 'ai', 'refund'])

export function legalTarget(id: string): DocId | null {
  if (isDocId(id)) return id
  if (mergedIntoRules.has(id)) return 'rules'
  return null
}

export type LegalDoc = {
  title: string
  mark: string
  principle: string
  zh: string[]
  en: string[]
  details: { heading: string; body: string }[]
}

export const legalDocs: Record<DocId, LegalDoc> = {
  rules: {
    title: '用户守则',
    mark: '📜 用户守则 (User Rules)',
    principle: '使用 PickGlobal 即表示您接受本守则。运营方为晨佑科学（深圳）有限公司。分析、线索和文案只是参考，不构成成交、利润、过关或合规承诺。',
    zh: [
      '您对上传的客户、员工和线索数据负责。我们只按您的指令提供工具，不代替您完成告知、同意或合规判断。',
      'AI 会出错、过时或编造。生成内容不是法律、税务、海关或广告审查意见。发送给客户前必须由人批准。金额以规则引擎为准。',
      '关税、平台规则、封号、汇率、物流、知识产权和坏账由您自行判断和承担。',
      '权益在微信或支付宝签名回调入账之后才生效。已交付的报告、额度和已批准消息，在法律允许的范围内不予退款。',
      '在法律允许的最大范围内，直接责任不超过您索赔前 12 个月已付费用；免费方案上限为人民币 100 元。',
    ],
    en: [
      'You are responsible for customer, staff, and lead data you upload. We provide tools on your instructions and do not obtain consent for you.',
      'AI can be wrong, stale, or invented. Output is not legal, tax, customs, or advertising advice. A person must approve anything sent to a customer. Amounts follow the rules engine.',
      'Duty, platform rules, account bans, FX, logistics, IP, and bad debt are your risks.',
      'Paid access starts only after the WeChat or Alipay callback clears. Delivered reports, quota, and approved messages are not refunded where the law allows.',
      'Where the law allows, direct liability is capped at fees paid in the prior 12 months, or RMB 100 on the free plan.',
    ],
    details: [
      { heading: '您的数据责任', body: '您是个人信息处理者，我们是受托处理方。每一条联系人应有合法依据，并已说明可能被用于商业触达。不要上传口令、完整银行卡号、证件影像、生物识别或未获同意的敏感个人信息。告知、同意、最小必要、保存期限、跨境提供，以及应答个人的查询、更正和删除，由您负责。账号被盗、误发或泄露时，由您通知受影响的人，并同时通知我们。' },
      { heading: '账号', body: '请自行保管账号，不得出借。因共享账号或弱口令造成的后果由您承担。违法、滥用或使我们面临监管风险时，我们可以暂停服务，这不免除您已经发生的责任。' },
      { heading: 'AI', body: '商品、线索和提示只用于当次生成，不用于训练 PickGlobal 自己的公开模型。为完成本次生成，内容可能交给模型服务商，其留存以其条款为准。请勿提交无权提供的资料。定价、报关、签约和客户沟通前请自行核对。把 AI 结果直接当作正式报价、广告或合规结论的后果由您承担。' },
      { heading: '商业风险', body: '关税、禁限、平台规则、封号、汇率、物流、货损、知识产权、广告法、客户投诉、拒付和坏账，都由您承担。是否采用建议、是否触达、是否成交，由您决定。服务按现状提供。在适用法律允许的最大范围内，我们不保证不中断、无错误，也不保证第三方平台、支付、短信或模型持续可用。' },
      { heading: '付款与退款', body: '价格、额度和账期以结算页为准。我们不保存完整卡号或支付口令。回调未成功前，付费额度、席位和功能不开通。发票按实际到账金额开具。到期未续费时，付费功能停止。已生成的报告、已消耗的额度、已批准发出的消息和已使用的席位视为已经交付。未开通的订单可申请原路退回。写信到 pickglobal@yeah.net，我们在 15 个工作日内回复。本规则不排除法律不能放弃的消费者或支付权利。' },
      { heading: '责任', body: '在适用法律允许的最大范围内，我们不对利润、商誉、数据丢失或间接损失负责。累计直接责任不超过索赔前 12 个月已实际支付的费用；免费用户上限为人民币 100 元。因您的内容、客户数据、违法使用、侵犯第三方，或把分析与 AI 结果直接当作正式报价、广告或合规结论而引起的索赔、罚款和合理费用，由您承担，并使晨佑科学（深圳）有限公司及其人员免受损失。法律强制不能排除的责任仍然保留。' },
      { heading: '法律', body: '适用中华人民共和国法律。争议由深圳市有管辖权的人民法院处理。' },
    ],
  },
  privacy: {
    title: '隐私条款',
    mark: '🔒 隐私政策 (Privacy Policy)',
    principle: '尊重并保护您的隐私是 PickGlobal（以下简称“我们”）的核心原则。运营方为晨佑科学（深圳）有限公司。',
    zh: [
      '存储位置：账号与业务数据存放在腾讯云 CloudBase（中国境内）。',
      '支付安全：不存储完整卡号或支付口令。微信、支付宝由对应机构处理，入账以后台签名回调为准。',
      'AI 交互：商品、线索和提示内容只用于当次分析或生成，不用于训练 PickGlobal 自己的公开模型。',
      '区域合规：可基于 IP 做访问与风控判断。',
      '数据权利：可要求导出、更正或删除账户数据。',
    ],
    en: [
      'Storage: Account and business data stay on Tencent CloudBase in mainland China.',
      'Payment safety: No full card data or payment secrets are stored. WeChat and Alipay process payments; credit follows the signed callback.',
      'AI usage: Product, lead, and prompt content is used for that generation, not to train a public PickGlobal model.',
      'Region checks: IP may be used for access and risk control.',
      'Your rights: You may ask to export, correct, or delete account data.',
    ],
    details: [
      { heading: '收集', body: '账户信息、企业名、商品与成本、线索和客户联系方式、账单与支付流水、邀请关系、配额与操作日志、IP 与设备信息。会话保存在这台浏览器。' },
      { heading: '用途', body: '提供选品分析与获客、计费、安全风控、通知和客服。我们不出售个人信息。处理限于您选用的功能。' },
      { heading: '共享', body: '仅在必要时与云基础设施、短信、邮件、支付机构和模型服务商共享，或按法律要求提供。这些是完成本功能所必需的分包方。模型服务商是否另作留存，以其自己的条款为准。如某次功能必须把数据交给境外模型或平台，仅传送完成本次所必需的字段。' },
      { heading: '存储与删除', body: '账户活跃期间保留。注销后删除账户资料与历史。对账、发票和审计记录按税法与监管要求继续保留。' },
      { heading: '安全', body: '传输使用 TLS。按租户隔离业务数据，并限制后台访问。' },
      { heading: '未成年人', body: '不面向 18 岁以下用户。如误收集，请联系我们删除。' },
      { heading: 'Cookies', body: '用于登录会话、界面偏好和必要的访问统计。' },
      { heading: '更新与联系', body: '重大变更会在登录时请您重新确认。问题或数据请求请联系 pickglobal@yeah.net，抄送 mornscience@sina.cn。' },
    ],
  },
}
