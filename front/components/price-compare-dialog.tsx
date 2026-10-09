'use client'

import { useEffect } from 'react'
import { createPortal } from 'react-dom'

export type PriceOffer = { name: string; price: string; currency: 'CNY' | 'USD' | string }
export type PriceSite = {
  id: string
  name: string
  region: string
  status: string
  count: number
  offers?: PriceOffer[]
}

const label: Record<string, string> = {
  ok: '已返回',
  failed: '调用失败',
  reauth: '需重新授权',
  skipped: '未配置',
}

function amount(price: string) {
  const value = Number(price)
  return Number.isFinite(value) ? value : 0
}

function SiteCard({ site }: { site: PriceSite }) {
  const offers = site.offers || []
  const peak = Math.max(0, ...offers.map((offer) => amount(offer.price)))
  const tone = site.status === 'ok' ? 'bg-emerald-600' : site.status === 'failed' || site.status === 'reauth' ? 'bg-amber-500' : 'bg-slate-400'
  return (
    <article className="rounded-2xl border border-border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium">{site.name}</h3>
        <span className={`rounded-full px-2 py-0.5 text-[11px] text-white ${tone}`}>{label[site.status] || site.status}</span>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">{site.region === 'CN' ? '中国供货 · 人民币' : '美国货架 · 美元'}</p>
      {offers.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-2">
          {offers.map((offer) => {
            const width = peak > 0 ? Math.max(8, Math.round((amount(offer.price) / peak) * 100)) : 0
            return (
              <li key={`${offer.name}-${offer.price}`}>
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="min-w-0 truncate">{offer.name}</span>
                  <span className="shrink-0 font-medium">{offer.currency === 'USD' ? `$${offer.price}` : `¥${offer.price}`}</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className={`h-full rounded-full ${site.region === 'CN' ? 'bg-blue-600' : 'bg-orange-500'}`} style={{ width: `${width}%` }} />
                </div>
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          {site.status === 'skipped' ? '这个站点还没有钥匙，所以没有价格。' : site.status === 'reauth' ? '授权过期了，需要重新登录后才能看到价格。' : '这次没有返回可比较的价格。'}
        </p>
      )}
    </article>
  )
}

export function PriceCompareDialog({
  query,
  sites,
  onClose,
}: {
  query: string
  sites: PriceSite[]
  onClose: () => void
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  const supply = sites.filter((site) => site.region === 'CN')
  const shelf = sites.filter((site) => site.region !== 'CN')
  const priced = sites.filter((site) => (site.offers || []).length > 0).length
  return createPortal(
    <div className="fixed inset-0 z-[90] flex items-end justify-center bg-slate-950/45 p-3 pb-[calc(5rem+env(safe-area-inset-bottom))] md:items-center md:p-6 md:pb-6" role="presentation" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="各站价格对照" className="max-h-[min(40rem,calc(100vh-6rem))] w-full max-w-3xl overflow-y-auto rounded-3xl bg-card p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-muted-foreground">各站价格对照</p>
            <h2 className="mt-1 text-lg font-semibold">{query || '这次搜索'}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{priced > 0 ? `${priced} 个站点返回了价格。蓝条是人民币进价，橙条是美元标价。` : '各站点都没有返回价格。下面是每个接口这次的结果。'}</p>
          </div>
          <button type="button" className="h-9 shrink-0 rounded-xl border border-border px-3 text-sm" onClick={onClose}>关闭</button>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <section>
            <h3 className="mb-2 text-sm font-medium">中国供货</h3>
            <div className="flex flex-col gap-2">{supply.map((site) => <SiteCard key={site.id} site={site} />)}</div>
          </section>
          <section>
            <h3 className="mb-2 text-sm font-medium">美国货架</h3>
            <div className="flex flex-col gap-2">{shelf.map((site) => <SiteCard key={site.id} site={site} />)}</div>
          </section>
        </div>
      </div>
    </div>,
    document.body,
  )
}
