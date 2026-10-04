'use client'

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

type Term = { title: string; body: string }

export const selectionTerms = {
  sku: { title: 'SKU', body: '商品编号。同一账号里不能重复。平台选品时，没有单独编号就用平台商品号。' },
  cost: { title: '采购成本', body: '付给国内供应商的货款，单位是人民币。选品排序用它当成本，不把美国标价当成进货价。' },
  price: { title: '售价', body: '准备在目标市场卖出的价格，单位是美元。利润率用净利润除以这个售价。' },
  packaging: { title: '包装', body: '包装费，人民币。和采购、国内运费一起按汇率换成美元，算进到岸成本。' },
  domestic: { title: '国内段', body: '从供应商到出口仓这一段运费，人民币。还没出境。' },
  international: { title: '国际段', body: '跨境运输费，美元。它超过售价的 35% 时，风险记为高。' },
  fx: { title: '汇率', body: '1 美元兑换多少人民币。人民币成本除以这个数，得到美元成本。优先用欧洲央行公布的即时汇率。' },
  route: { title: '路线', body: '货从哪个国家发到哪个市场，例如中国到美国。改路线、市场或成本后，旧报告过期，必须重新分析。' },
  incoterm: { title: '贸易术语', body: '交货时费用算到谁头上。DDP 是完税后交货：关税、运费都算进到岸成本，买家不再另付这些。' },
  tax: { title: '税务口径', body: '用哪一套关税和增值税。中国到美国是 cn_us，关税 7.5%，增值税 0。香港无关税，澳大利亚另有关税和增值税。' },
  floor: { title: '利润线', body: '售价至少要到这条线，扣完采购、运费、平台费、支付费和税之后，还剩 15% 利润。低于它就不按市场价卖。' },
  margin: { title: '利润率', body: '净利润除以售价。达到 15%，并且风险不是高，才标成优先。' },
  score: { title: '机会分', body: '利润率乘以 160，限制在 0 到 100。风险为高再减 15。这是规则算的，不是模型打分。' },
  risk: { title: '风险', body: '利润率低于 5%，或国际运费超过售价的 35%，就是高。否则利润率低于 15% 是中，其余是低。' },
  median: { title: '中位价', body: '把同类报价从小到大排列，取正中间。偶数条时取中间两条的平均。国内中位价再除以汇率换成美元。' },
  listed: { title: '标价', body: '你现在标出去的售价。它和海外中位价相差超过 5%，会标成低于市场或高于市场。' },
  recommended: { title: '建议售价', body: '有海外中位价而且它不低于利润线时，用中位价。否则用利润线。没有海外价时，标价已经够高就保持标价。' },
  pick: { title: '优先', body: '同时满足两件事：利润率至少 15%，风险不是高。只满足一项的标成暂缓。' },
  rules: { title: '规则版本', body: '金额只用 pg-rules-1.0 这一套公式。模型可以写解释，不能改利润、税、时效和风险。' },
  acquire: { title: '一键获客', body: '把这份报告交给获客。报告过期时点不了。第一次点击记下时间，再次点击不会重复记。' },
  stale: { title: '报告过期', body: '商品的市场、成本、运费、售价或汇率改过之后，旧报告只读。要重新分析，才能再获客。' },
  profit: { title: '净利润', body: '售价减去到岸成本、渠道费和税。到岸成本含采购、包装、国内段和国际段。' },
  duty: { title: '关税', body: '按采购加国际运费，再乘关税率。中国到美国的关税率是 7.5%。' },
  vat: { title: '增值税', body: '按售价乘增值税率。中国到美国这条口径是 0。国内销售是 13%，到澳大利亚是 10%。' },
  fee: { title: '渠道费', body: '平台费加支付费。美国平台费 15%，支付费一律 2.9%，都按售价计算。' },
  hs: { title: 'HS 编码', body: '海关给商品分类用的编码提示。只改它或名称、类目，不会让旧报告过期。' },
  origin: { title: '货源', body: '商品从哪个国家发出。默认是中国。' },
  market: { title: '目标市场', body: '商品要卖到哪里。美国查亚马逊、沃尔玛和 eBay 的在售价。改市场后要重新分析。' },
  transit: { title: '时效', body: '这条路线预计几天能到。中国到美国按 12 到 20 天。它和利润同一次算出来，不再单独估算。' },
  four: { title: '四维', body: '利润、税务、时效、风险。四个数来自同一次计算，报告只是把它们分开显示。' },
  selection: { title: '帮我选品', body: '用关键词查中国供货和美国货架。供货价是成本，美国在售价的中位数是售价，再按利润规则排序。平台没配钥匙就用本地演示目录。' },
  analyze: { title: '分析', body: '按当前商品的成本、售价和路线重算一遍，生成报告。数字以规则为准。改过市场或成本后要再分析一次。' },
  position: { title: '位置', body: '标价比海外中位价低过 5% 是低于市场，高过 5% 是高于市场，中间是贴近。没有海外价就写无海外报价。' },
  provider: { title: '货源来源', body: '任一中国或美国平台返回商品时是实时。全部没钥匙或都失败时，退回本地演示目录。' },
} satisfies Record<string, Term>

export type SelectionTermId = keyof typeof selectionTerms

export function TermHint({ id }: { id: SelectionTermId }) {
  const [open, setOpen] = useState(false)
  const term = selectionTerms[id]
  useEffect(() => {
    if (!open) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])
  return (
    <>
      <button
        type="button"
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-border text-[10px] leading-none text-muted-foreground"
        aria-label={`${term.title}是什么`}
        onClick={(event) => {
          event.preventDefault()
          event.stopPropagation()
          setOpen(true)
        }}
      >
        ?
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-label={term.title} onClick={() => setOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-card p-5 shadow-xl" onClick={(event) => event.stopPropagation()}>
            <h2 className="text-base font-semibold">{term.title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{term.body}</p>
            <button type="button" className="mt-4 h-10 w-full rounded-xl bg-primary text-sm font-medium text-primary-foreground" onClick={() => setOpen(false)}>
              知道了
            </button>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
