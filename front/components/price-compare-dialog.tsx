'use client'

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'

export type PriceOffer = { name: string; price: string; currency: 'CNY' | 'USD' | string }
export type PriceSite = {
  id: string
  name: string
  region: string
  status: string
  count: number
  offers?: PriceOffer[]
}

const SUPPORT_EMAIL = 'pickglobal@yeah.net'

const label: Record<string, string> = {
  ok: '已返回',
  failed: '调用失败',
  reauth: '需重新授权',
  skipped: '当前版本未上线',
}

type MailDraft = { subject: string; body: string }

function supportDraft(offline: string[]): MailDraft {
  const names = offline.length ? offline.join('、') : '相关平台'
  return {
    subject: `请尽快上线选品平台：${names}`,
    body: `你好，我在 PickGlobal「帮我选品」里看到以下平台当前版本尚未上线：${names}。\n请尽快接入并上线，方便比价选品。谢谢。\n`,
  }
}

/** Domestic webmail home pages (compose deep-links 404 / timeout in CN). */
const WEBMAIL_HOMES = [
  { id: 'qq', name: 'QQ 邮箱', href: 'https://mail.qq.com/' },
  { id: '163', name: '163 邮箱', href: 'https://mail.163.com/' },
  { id: '126', name: '126 邮箱', href: 'https://mail.126.com/' },
  { id: 'yeah', name: 'yeah 邮箱', href: 'https://mail.yeah.net/' },
] as const

function systemMailto(draft: MailDraft) {
  const subject = encodeURIComponent(draft.subject)
  const body = encodeURIComponent(draft.body)
  return `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`
}

function amount(price: string) {
  const value = Number(price)
  return Number.isFinite(value) ? value : 0
}

function SiteCard({ site, offerLimit }: { site: PriceSite; offerLimit: number }) {
  const offers = (site.offers || []).slice(0, offerLimit)
  const [open, setOpen] = useState(false)
  const peak = Math.max(0, ...offers.map((offer) => amount(offer.price)))
  const tone = site.status === 'ok' ? 'bg-emerald-600' : site.status === 'failed' || site.status === 'reauth' ? 'bg-amber-500' : 'bg-slate-400'
  const collapsible = offers.length > 0
  return (
    <article className="rounded-2xl border border-border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        {collapsible ? (
          <button
            type="button"
            className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            <h3 className="font-medium">{site.name}</h3>
            <span className="text-[11px] text-muted-foreground">{open ? '收起' : `展开 ${offers.length} 条`}</span>
            {open ? <ChevronUp className="size-3.5 shrink-0 text-muted-foreground" /> : <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />}
          </button>
        ) : (
          <h3 className="font-medium">{site.name}</h3>
        )}
        <span className={`rounded-full px-2 py-0.5 text-[11px] text-white ${tone}`}>{label[site.status] || site.status}</span>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">{site.region === 'CN' ? '中国供货 · 人民币' : '美国货架 · 美元'}</p>
      {offers.length > 0 ? (
        open ? (
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
            <li>
              <button type="button" className="text-[11px] text-muted-foreground underline-offset-2 hover:underline" onClick={() => setOpen(false)}>
                收起结果
              </button>
            </li>
          </ul>
        ) : (
          <p className="mt-3 text-xs leading-5 text-muted-foreground">已返回 {offers.length} 条，点击上方展开查看。</p>
        )
      ) : (
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          {site.status === 'skipped'
            ? '当前版本尚未上线该平台，暂时没有价格。'
            : site.status === 'reauth'
              ? '授权过期了，需要重新登录后才能看到价格。'
              : '这次没有返回可比较的价格。'}
        </p>
      )}
    </article>
  )
}

function SupportMailPanel({ offline }: { offline: string[] }) {
  const draft = supportDraft(offline)
  const [copied, setCopied] = useState(false)
  const [hint, setHint] = useState('')

  async function copyDraft() {
    const text = `收件人：${SUPPORT_EMAIL}\n主题：${draft.subject}\n\n${draft.body}`
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
      return true
    } catch {
      setHint('复制失败，请长按选中上方邮箱与主题手动复制。')
      return false
    }
  }

  async function openWebmail(href: string, name: string) {
    const ok = await copyDraft()
    if (ok) setHint(`已复制正文。在 ${name} 点「写邮件」，粘贴收件人与内容即可。`)
    window.open(href, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/80 px-3 py-3 text-sm leading-6 text-amber-950">
      <p>
        {offline.join('、')} 在当前版本尚未上线。请发信催我们尽快接入：
        <span className="font-medium"> {SUPPORT_EMAIL}</span>
      </p>
      <p className="mt-1 text-[11px] text-amber-900/80">主题：{draft.subject}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <a
          href={systemMailto(draft)}
          className="inline-flex h-9 items-center justify-center rounded-xl bg-amber-900 px-3 text-xs font-medium text-amber-50"
          title="Outlook / Foxmail / 系统自带邮件"
        >
          系统邮箱
        </a>
        <button
          type="button"
          className="inline-flex h-9 items-center justify-center gap-1 rounded-xl border border-amber-900/30 bg-white/70 px-3 text-xs font-medium text-amber-950"
          onClick={() => {
            void copyDraft().then((ok) => {
              if (ok) setHint('已复制收件人、主题和正文，打开任意邮箱粘贴发送。')
            })
          }}
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? '已复制' : '复制全文'}
        </button>
        {WEBMAIL_HOMES.map((item) => (
          <button
            key={item.id}
            type="button"
            className="inline-flex h-9 items-center justify-center rounded-xl bg-amber-900 px-3 text-xs font-medium text-amber-50"
            onClick={() => void openWebmail(item.href, item.name)}
          >
            {item.name}
          </button>
        ))}
      </div>
      <p className="mt-2 text-[11px] leading-5 text-amber-900/80">
        {hint || '国内网页邮箱没有稳定的「一键写邮件」链接。点 QQ / 163 / 126 / yeah 会先复制全文再打开邮箱首页，登录后写邮件并粘贴即可。系统邮箱走本机客户端。'}
      </p>
    </div>
  )
}

export function PriceCompareDialog({
  query,
  sites,
  offerLimit = 5,
  onClose,
}: {
  query: string
  sites: PriceSite[]
  offerLimit?: number
  onClose: () => void
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  const limit = Math.min(30, Math.max(1, offerLimit))
  const supply = sites.filter((site) => site.region === 'CN')
  const shelf = sites.filter((site) => site.region !== 'CN')
  const priced = sites.filter((site) => (site.offers || []).length > 0).length
  const offline = sites.filter((site) => site.status === 'skipped').map((site) => site.name)
  return createPortal(
    <div className="fixed inset-0 z-[90] flex items-end justify-center bg-slate-950/45 p-3 pb-[calc(5rem+env(safe-area-inset-bottom))] md:items-center md:p-6 md:pb-6" role="presentation" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="各站价格对照" className="max-h-[min(40rem,calc(100vh-6rem))] w-full max-w-3xl overflow-y-auto rounded-3xl bg-card p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-muted-foreground">各站价格对照</p>
            <h2 className="mt-1 text-lg font-semibold">{query || '这次搜索'}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{priced > 0 ? `${priced} 个站点返回了价格。每个站点最多 ${limit} 条。蓝条是人民币进价，橙条是美元标价。有结果的站点可折叠。` : '各站点都没有返回价格。下面是每个接口这次的结果。'}</p>
          </div>
          <button type="button" className="h-9 shrink-0 rounded-xl border border-border px-3 text-sm" onClick={onClose}>关闭</button>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <section>
            <h3 className="mb-2 text-sm font-medium">中国供货</h3>
            <div className="flex flex-col gap-2">{supply.map((site) => <SiteCard key={site.id} site={site} offerLimit={limit} />)}</div>
          </section>
          <section>
            <h3 className="mb-2 text-sm font-medium">美国货架</h3>
            <div className="flex flex-col gap-2">{shelf.map((site) => <SiteCard key={site.id} site={site} offerLimit={limit} />)}</div>
          </section>
        </div>
        {offline.length > 0 && <SupportMailPanel offline={offline} />}
      </div>
    </div>,
    document.body,
  )
}
