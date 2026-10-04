'use client'

import { useState } from 'react'
import { createPortal } from 'react-dom'

export const LEGAL_VERSION = '2026-10-04'

type DocId = 'privacy' | 'cio' | 'terms'

const docs: Record<DocId, { title: string; sections: { heading: string; body: string }[] }> = {
  privacy: {
    title: '隐私政策',
    sections: [
      { heading: '谁在处理', body: 'PickGlobal 由晨佑科学（深圳）有限公司运营。你注册、登录或使用工作台，即由我们按本政策处理你的个人信息。联系 pickglobal@yeah.net。' },
      { heading: '我们收集什么', body: '账号资料（姓名、邮箱、手机、企业名）、登录与设备日志、你上传的商品与成本、线索和客户联系方式、账单与支付流水、邀请关系，以及为安全保存的操作记录。会话保存在这台浏览器。' },
      { heading: '用来做什么', body: '用于开通账号、选品分析、获客、计费、安全、客服和履行法定义务。我们不出售个人信息。' },
      { heading: '交给谁', body: '在完成本次服务所必需时，数据会交给云主机、数据库、短信、邮件、支付和模型服务商。他们只应按我们的指示处理。法律法规要求时，我们会向主管机关提供。' },
      { heading: '存放与期限', body: '数据放在为 PickGlobal 配置的云环境中。账号存续期间保留。你注销后删除账号资料；交易、发票和审计记录按税法与监管要求继续保留。' },
      { heading: '你的权利', body: '你可以查询、更正、导出或要求删除你的账号资料，也可以撤回同意。撤回后我们可能无法继续提供依赖该数据的功能。行使权利请发邮件到 pickglobal@yeah.net。' },
      { heading: '未成年人', body: '本服务面向具备完全民事行为能力的经营者，不向未满 18 周岁的人提供。' },
    ],
  },
  cio: {
    title: 'CIO 合规',
    sections: [
      { heading: '角色', body: '你（以及你的企业、你指定的信息负责人或 CIO）是你上传的商品、员工、客户和线索数据的个人信息处理者。我们是按你的指令提供工具的受托方，不代替你做合法性判断。' },
      { heading: '你的信息责任', body: '你负责告知、同意、最小必要、目的限制、保存期限、跨境提供和应答个人权利请求。你保证对每一条客户或联系人数据都有合法依据，并已向对方说明可能被用于商业触达。' },
      { heading: '不得上传的内容', body: '不要提交你无权处理的保密信息、账号口令、完整支付卡号、身份证影像、生物识别或未获同意的敏感个人信息。因此产生的投诉、调查和赔偿由你承担。' },
      { heading: '分包与安全', body: '我们使用云、支付、短信、邮件和模型服务商。你应自行保管账号，不得出借。发现泄露、被盗或误发，应立即通知我们并自行通知受影响的个人。' },
      { heading: '中止', body: '若你的处理活动违法、侵害他人或使我们面临监管风险，我们可以暂停或终止服务，并在法律要求时配合调查。这不免除你已经发生的责任。' },
    ],
  },
  terms: {
    title: '用户协议',
    sections: [
      { heading: '服务是什么', body: 'PickGlobal 提供选品分析与获客工具。它不是律师、会计师、报关行、券商或平台官方。报告、价格、线索和文案都只是参考，不构成成交、利润、过关或合规的承诺。' },
      { heading: 'AI 风险由你承担', body: '模型会出错、过时或编造。生成内容不是法律、税务、海关、医疗、金融或广告审查意见。你必须人工核对后再定价、签约、报关或联系客户。为完成本次生成，你提交的内容可能发送给模型服务商。请勿提交无权提供的资料。我们不保证模型服务商如何留存这些内容。金额以规则引擎的结果为准，输入错误会导致结果不可用。' },
      { heading: '商业风险由你承担', body: '关税、禁限、平台规则、封号、汇率、物流、货损、知识产权、广告法、反不正当竞争、客户投诉、拒付和坏账，都由你自行判断和承担。你决定是否采用任何建议、是否发送任何触达、是否成交。' },
      { heading: '按现状提供', body: '在适用法律允许的最大范围内，服务按现状和可用状态提供。我们不保证不中断、无错误、适合你的特定商品或市场，也不保证第三方平台、支付、短信或模型持续可用。' },
      { heading: '责任限制', body: '在适用法律允许的最大范围内，我们不对利润损失、商誉、数据丢失、间接或后果性损害负责。我们的累计直接责任不超过你在索赔前 12 个月就本服务已实际支付的费用；若你使用免费方案，上限为人民币 100 元。法律强制不能排除的责任仍然保留。' },
      { heading: '你应赔偿我们', body: '因你的内容、客户数据、违法使用、侵犯第三方，或把 AI 结果、分析报告直接当作正式报价、广告或合规结论而引起的索赔、罚款和合理费用，由你承担，并使晨佑科学（深圳）有限公司及其人员免受损失。' },
      { heading: '法律', body: '本协议适用中华人民共和国法律。争议由深圳市有管辖权的人民法院处理。本版生效日期 2026-10-04。' },
    ],
  },
}

export function LegalConsent({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  const [open, setOpen] = useState<DocId | null>(null)
  const doc = open ? docs[open] : null
  return (
    <div className="mt-3">
      <div className="flex items-start gap-2">
        <input
          id="legal-accept"
          type="checkbox"
          className="mt-0.5 size-3.5 shrink-0"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
        />
        <p className="text-left leading-5 text-muted-foreground">
          <label htmlFor="legal-accept">我已阅读并同意</label>
          {(Object.keys(docs) as DocId[]).map((id, index) => (
            <span key={id}>
              {index === 0 ? '' : index === 2 ? '和' : '、'}
              <button type="button" className="text-primary underline" onClick={() => setOpen(id)}>《{docs[id].title}》</button>
            </span>
          ))}
          。商业风险、数据责任和 AI 风险由我自行承担。
        </p>
      </div>
      {doc && createPortal(
        <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-3 pb-[calc(5rem+env(safe-area-inset-bottom))] md:items-center md:p-4 md:pb-4" onClick={() => setOpen(null)}>
          <div className="flex max-h-[min(70dvh,32rem)] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-blue-100 bg-card text-sm text-foreground shadow-2xl" onClick={(event) => event.stopPropagation()} role="dialog" aria-label={doc.title}>
            <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
              <h2 className="text-base font-semibold">{doc.title}</h2>
              <button type="button" className="rounded-lg px-2 py-1 text-sm text-muted-foreground" onClick={() => setOpen(null)}>关闭</button>
            </div>
            <div className="flex gap-2 overflow-x-auto px-4 pt-3">
              {(Object.keys(docs) as DocId[]).map((id) => (
                <button key={id} type="button" className={`h-8 shrink-0 rounded-full px-3 text-xs font-semibold ${open === id ? 'bg-blue-600 text-white' : 'border border-blue-100 bg-white text-slate-700'}`} onClick={() => setOpen(id)}>{docs[id].title}</button>
              ))}
            </div>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-4 py-3">
              {doc.sections.map((section) => (
                <section key={section.heading}>
                  <h3 className="font-semibold">{section.heading}</h3>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">{section.body}</p>
                </section>
              ))}
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}

export function rememberLegalAcceptance() {
  window.localStorage.setItem('pickglobal.legal', JSON.stringify({ version: LEGAL_VERSION, at: new Date().toISOString() }))
}
