'use client'

import { useEffect, useState } from 'react'
import { api, percent, waitJob } from '@/lib/api'
import { ProductLibrary } from '@/components/product-library'
import { PriceCompareDialog, type PriceSite } from '@/components/price-compare-dialog'
import { ReportDialog } from '@/components/report-dialog'
import { ResultDesk } from '@/components/result-desk'
import { RouteBar } from '@/components/route-bar'
import { TermHint, type SelectionTermId } from '@/components/term-hint'
import { readTradeRoute, TRADE_ROUTES } from '@/lib/trade-route'

type Selection = {
  pick: boolean
  score: number
  net_margin: string
  risk_level: string
  reason: string
}

type PlatformStatus = PriceSite

type ShelfRefresh = { interval_seconds: number; premium: boolean; manual_left: number; fresh: boolean }

type ShelfPayload = { items: CatalogItem[]; sources?: { provider?: string; platforms?: PlatformStatus[]; refresh?: ShelfRefresh } }

type CatalogItem = {
  id: string
  name: string
  sku: string
  category: string
  cost_cny: string
  target_price_usd: string
  supplier: string
  platform?: string
  price_basis?: string
  selection?: Selection
}

type Quote = {
  sku: string
  name: string
  listed_price_usd: string
  recommended_price_usd: string
  floor_price_usd: string
  position: string
  advice: string
  domestic: { median: string | null; currency: string; count: number }
  overseas: { median: string | null; currency: string; market: string; count: number }
  report: {
    profit: { net_margin: string; net_profit_usd?: string }
    tax?: { tax_usd: string }
    time?: { transit_days_min: number; transit_days_max: number }
    risk: { risk_level: string }
  }
  market_feed?: {
    strategy: string
    fx?: { provider: string; rate?: string; used?: boolean }
    offers?: { provider: string; count?: number }
  }
}

const positionLabel: Record<string, string> = {
  below_market: '低于海外中位',
  in_band: '贴近海外中位',
  above_market: '高于海外中位',
  no_overseas_comp: '无海外报价',
}

const emptyForm = {
  name: '样品杯',
  sku: 'CUP-1',
  category: '家居',
  cost_cny: '72',
  packaging_cny: '4',
  domestic_freight_cny: '6',
  international_freight_usd: '3.2',
  target_price_usd: '39',
  origin_country: 'CN',
  target_market: 'US',
  route: 'CN-US',
  incoterm: 'DDP',
  tax_regime: 'cn_us',
  cost_currency: 'CNY',
  price_currency: 'USD',
  fx_usd_cny: '7.20',
  hs_code_hint: '',
}

function tsvToCsv(text: string) {
  return text.split(/\r?\n/).map((line) => {
    if (!line.includes('\t')) return line
    return line.split('\t').map((cell) => {
      const value = cell.trim()
      return /[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value
    }).join(',')
  }).join('\n')
}

async function spreadsheetToCsv(file: File) {
  const name = file.name.toLowerCase()
  if (/\.(xlsx|xls|xlsm)$/.test(name)) {
    const XLSX = await import('xlsx')
    const book = XLSX.read(await file.arrayBuffer())
    const sheet = book.Sheets[book.SheetNames[0]]
    if (!sheet) throw new Error('这个表格没有工作表')
    const text = XLSX.utils.sheet_to_csv(sheet)
    if (!text.trim()) throw new Error('这个表格是空的')
    return text
  }
  const text = await file.text()
  if (name.endsWith('.tsv') || (text.includes('\t') && !text.slice(0, 400).includes(','))) return tsvToCsv(text)
  return text
}

export default function ProductsPage() {
  const [tab, setTab] = useState<'entry' | 'catalog' | 'library'>('entry')
  const [form, setForm] = useState(emptyForm)
  const [csv, setCsv] = useState('sku,name,cost_cny,target_price_usd,international_freight_usd\nCUP-1,样品杯,72,40,2\n')
  const [csvFile, setCsvFile] = useState('')
  const [catalog, setCatalog] = useState<CatalogItem[]>([])
  const [provider, setProvider] = useState('')
  const [platforms, setPlatforms] = useState<PlatformStatus[]>([])
  const [refresh, setRefresh] = useState<ShelfRefresh | null>(null)
  const [shelfQuery, setShelfQuery] = useState('')
  const [compareOpen, setCompareOpen] = useState(false)
  const [libraryKey, setLibraryKey] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [quotes, setQuotes] = useState<Quote[]>([])
  const [quoteOpen, setQuoteOpen] = useState(false)
  const [quoteIndex, setQuoteIndex] = useState(0)
  const [route, setRoute] = useState(readTradeRoute())

  useEffect(() => {
    function apply() {
      const next = readTradeRoute()
      const spec = TRADE_ROUTES[next]
      setRoute(next)
      setForm((current) => ({
        ...current,
        origin_country: spec.origin_country,
        target_market: spec.target_market,
        tax_regime: spec.tax_regime,
        route: spec.route,
      }))
    }
    apply()
    window.addEventListener('pickglobal-route', apply)
    return () => window.removeEventListener('pickglobal-route', apply)
  }, [])

  function setField(key: keyof typeof emptyForm, value: string) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await action()
      setLibraryKey((current) => current + 1)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '操作失败')
    } finally {
      setBusy(false)
    }
  }

  const views = [
    { id: 'entry', name: '录入' },
    { id: 'catalog', name: '帮我选品' },
    { id: 'library', name: '已入库' },
  ] as const

  return (
    <div className="work-desk flex flex-col gap-2 overflow-hidden">
      <RouteBar />
      <div className="shrink-0">
        <h1 className="text-lg font-semibold tracking-tight sm:text-xl">双向入口，同一商品库</h1>
        <p className="hidden text-xs leading-5 text-muted-foreground sm:block">一条一条写，或用 CSV、TSV、Excel 一次导入。</p>
      </div>
      {error && <p className="shrink-0 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      {message && <p className="shrink-0 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p>}
      <div className="grid shrink-0 grid-cols-3 gap-2">
        {views.map((item) => (
          <button key={item.id} type="button" className={`h-9 rounded-xl px-2 text-sm font-medium ${tab === item.id ? 'bg-blue-600 text-white' : 'border border-border bg-white text-slate-700 dark:bg-card dark:text-foreground'}`} onClick={() => setTab(item.id)}>
            {item.name}
          </button>
        ))}
      </div>
      <section className="panel-frame min-h-0 flex-1 overflow-y-auto rounded-2xl bg-card p-3 md:p-4">
      {tab === 'entry' ? (
          <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
          <form onSubmit={(event) => {
            event.preventDefault()
            void run(async () => {
              await api('/products', { method: 'POST', body: JSON.stringify(form) })
              setMessage('商品已入库，可以开始分析。')
            })
          }}>
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">手动录入</h2>
              <button disabled={busy} className="h-8 shrink-0 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground disabled:opacity-50">写入商品库</button>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-x-2 gap-y-1.5 lg:grid-cols-2 xl:grid-cols-3">
              <Field label="名称" value={form.name} onChange={(value) => setField('name', value)} />
              <Field label="SKU" hint="sku" value={form.sku} onChange={(value) => setField('sku', value)} />
              <Field label="采购成本 CNY" hint="cost" value={form.cost_cny} onChange={(value) => setField('cost_cny', value)} />
              <Field label="售价 USD" hint="price" value={form.target_price_usd} onChange={(value) => setField('target_price_usd', value)} />
              <Field label="包装 CNY" hint="packaging" value={form.packaging_cny} onChange={(value) => setField('packaging_cny', value)} />
              <Field label="国内段 CNY" hint="domestic" value={form.domestic_freight_cny} onChange={(value) => setField('domestic_freight_cny', value)} />
              <Field label="国际段 USD" hint="international" value={form.international_freight_usd} onChange={(value) => setField('international_freight_usd', value)} />
              <Field label="汇率 USD/CNY" hint="fx" value={form.fx_usd_cny} onChange={(value) => setField('fx_usd_cny', value)} />
              <Field label="贸易术语" hint="incoterm" value={form.incoterm} onChange={(value) => setField('incoterm', value)} />
            </div>
          </form>
          <form className="border-t border-border pt-3 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0" onSubmit={(event) => {
            event.preventDefault()
            void run(async () => {
              const created = await api<{ job_id: string }>('/products/imports', { method: 'POST', body: JSON.stringify({ csv, algorithm: 'product-pricer', route }) })
              const job = await waitJob(created.job_id)
              if (job.status === 'failed') throw new Error(job.error?.message || '导入失败')
              const priced = job.result as { imported?: number; failed?: number; quotes?: Quote[] } | null
              const next = priced?.quotes ?? []
              setQuotes(next)
              setQuoteIndex(0)
              setQuoteOpen(next.length > 0)
              setMessage(`表格导入完成：成功 ${priced?.imported ?? 0}，失败 ${priced?.failed ?? 0}。定价算法已比对国内外报价。`)
            })
          }}>
            <h2 className="text-sm font-semibold">表格导入</h2>
            <p className="mt-0.5 line-clamp-1 text-[11px] leading-4 text-muted-foreground">表头要有 sku、name、cost_cny、target_price_usd。写入当前起源地和目标地。</p>
            <textarea className="mt-1.5 h-12 w-full rounded-lg bg-muted p-2 font-mono text-xs sm:h-24" value={csv} onChange={(event) => setCsv(event.target.value)} />
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <label className="inline-flex h-8 cursor-pointer items-center justify-center rounded-lg border border-border px-3 text-sm">
                上传文件
                <input
                  type="file"
                  accept=".csv,.tsv,.txt,.xlsx,.xls,.xlsm,text/csv,text/tab-separated-values,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    event.target.value = ''
                    if (!file) return
                    setCsvFile(file.name)
                    void spreadsheetToCsv(file).then((text) => setCsv(text)).catch((reason: Error) => setError(reason.message || '无法读取这个文件'))
                  }}
                />
              </label>
              <button disabled={busy} className="h-8 rounded-lg bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50">开始导入</button>
              <button
                type="button"
                disabled={busy}
                className="h-8 rounded-lg border border-border px-3 text-sm disabled:opacity-50"
                onClick={() => {
                void run(async () => {
                  const priced = await api<{ items: Quote[] }>('/algorithms/product-pricer', { method: 'POST', body: JSON.stringify({ csv, route_id: route }) })
                  setQuotes(priced.items)
                  setQuoteIndex(0)
                  setQuoteOpen(priced.items.length > 0)
                  setMessage(priced.items.length ? `已比对 ${priced.items.length} 条售价。` : '没有可比对的商品行。')
                })
              }}
              >先比价，不入库</button>
              {csvFile && <span className="text-xs text-muted-foreground">{csvFile}</span>}
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground"><span className="font-semibold text-primary">国内外商品定价</span> 对照货架价给建议售价<TermHint id="recommended" />，不低于 15% 利润线<TermHint id="floor" />。</p>
            {quotes.length > 0 && (
              <button type="button" className="mt-3 text-sm text-primary" onClick={() => setQuoteOpen(true)}>
                阅读利润报告（{quotes.length}）
              </button>
            )}
          </form>
          </div>
      ) : tab === 'catalog' ? (
        <div>
          <h2 className="font-semibold inline-flex items-center">帮我选品<TermHint id="selection" /></h2>
          <div className="mt-1 text-sm text-muted-foreground">按{TRADE_ROUTES[route].label}比价。利润率<TermHint id="margin" />达到 15% 且风险<TermHint id="risk" />不是高的商品优先<TermHint id="pick" />。</div>
          {platforms.length > 0 && (
            <div className="mt-2 text-xs leading-5 text-muted-foreground">
              {platforms.map((item) => `${item.name}${item.status === 'ok' ? ` ${item.count}` : item.status === 'failed' ? ' 失败' : item.status === 'reauth' ? ' 需重新授权' : ' 未配置'}`).join(' · ')}
              {' · '}来源 {provider === 'live' ? '实时' : '本地演示'}<TermHint id="provider" />
            </div>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{refresh?.premium ? '1688 价格每 15 分钟更新。' : '1688 价格每小时更新。支付成长或规模后改为每 15 分钟，并有 10 次随时刷新。'}</span>
            {refresh?.premium ? <span>还可随时刷新 {refresh.manual_left} 次。</span> : <a className="text-primary" href="/workspace/billing">去支付</a>}
            {refresh?.premium && shelfQuery && (
              <button
                type="button"
                disabled={busy || refresh.manual_left <= 0}
                className="h-8 rounded-lg border border-border px-2 text-xs disabled:opacity-50"
                onClick={() => {
                  void run(async () => {
                    const data = await api<ShelfPayload>(`/catalog/refresh?q=${encodeURIComponent(shelfQuery)}&route=${route}`, { method: 'POST' })
                    setCatalog(data.items)
                    setProvider(data.sources?.provider || '')
                    setPlatforms(data.sources?.platforms || [])
                    setRefresh(data.sources?.refresh || null)
                    setCompareOpen(true)
                    setMessage(data.sources?.refresh?.fresh ? '已向 1688 要到新价格。' : '用的是刚才的价格。')
                  })
                }}
              >立即刷新</button>
            )}
          </div>
          <div className="mt-3">
            <ResultDesk
              items={catalog}
              placeholder="搜索名称、SKU 或供应商"
              keywords={(item) => `${item.name} ${item.sku} ${item.supplier} ${item.category}`}
              onSearch={(next) => {
                void run(async () => {
                  const data = await api<ShelfPayload>(`/catalog/search?q=${encodeURIComponent(next)}&algorithm=selection-assist&route=${route}`)
                  setShelfQuery(next)
                  setCatalog(data.items)
                  setProvider(data.sources?.provider || '')
                  setPlatforms(data.sources?.platforms || [])
                  setRefresh(data.sources?.refresh || null)
                  setCompareOpen(true)
                })
              }}
              filters={[{ key: 'pick', label: '建议', value: (item) => item.selection?.pick ? '优先' : '暂缓' }]}
              sorts={[
                { id: 'score', label: '机会分', compare: (left, right) => (right.selection?.score || 0) - (left.selection?.score || 0) },
                { id: 'margin', label: '利润率', compare: (left, right) => (right.selection?.net_margin || '').localeCompare(left.selection?.net_margin || '') },
                { id: 'name', label: '名称', compare: (left, right) => left.name.localeCompare(right.name, 'zh') },
              ]}
              searching={busy}
              empty={busy ? '正在向各平台询价…' : platforms.length > 0 ? '各平台没有可入库的商品。比价窗口里是每个站点这次的返回。' : '还没有货源结果。输入关键词后搜索。'}
              render={(item) => (
                <article className="rounded-xl border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="font-medium">{item.name}</h3>
                      <div className="mt-1 text-xs text-muted-foreground">{item.platform || item.supplier} · <span className="inline-flex items-center">SKU {item.sku}<TermHint id="sku" /></span> · ¥{item.cost_cny} · ${item.target_price_usd}{item.price_basis === 'us_shelf' ? ' 美国货架' : item.price_basis === 'floor_reference' ? ' 利润线' : ''}</div>
                      {item.selection && <div className="mt-1 text-xs text-muted-foreground">{item.selection.pick ? '优先' : '暂缓'}<TermHint id="pick" /> · 机会分 {item.selection.score}<TermHint id="score" /> · 利润率 {item.selection.net_margin}<TermHint id="margin" /> · 风险 {item.selection.risk_level}<TermHint id="risk" /></div>}
                    </div>
                    <button type="button" disabled={busy} className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => {
                      void run(async () => {
                        await api('/catalog/adopt', { method: 'POST', body: JSON.stringify({ catalog_id: item.id, route }) })
                        setMessage(`${item.name} 已进入商品库。`)
                      })
                    }}>入库</button>
                  </div>
                </article>
              )}
            />
          </div>
          {compareOpen && <PriceCompareDialog query={shelfQuery} sites={platforms} onClose={() => setCompareOpen(false)} />}
        </div>
      ) : (
        <div>
          <h2 className="font-semibold inline-flex items-center">已入库商品<TermHint id="analyze" /></h2>
          <div className="mt-1 text-sm text-muted-foreground">当前 {TRADE_ROUTES[route].label}。分析会按这条路线重算。</div>
          <div className="mt-3">
            <ProductLibrary key={libraryKey} />
          </div>
        </div>
      )}
      </section>
      {quoteOpen && quotes[quoteIndex] && (
        <ReportDialog title="利润报告" onClose={() => setQuoteOpen(false)}>
          <ProfitReport
            quote={quotes[quoteIndex]}
            index={quoteIndex}
            total={quotes.length}
            onPrev={() => setQuoteIndex((current) => Math.max(0, current - 1))}
            onNext={() => setQuoteIndex((current) => Math.min(quotes.length - 1, current + 1))}
          />
        </ReportDialog>
      )}
    </div>
  )
}

function ProfitReport({
  quote,
  index,
  total,
  onPrev,
  onNext,
}: {
  quote: Quote
  index: number
  total: number
  onPrev: () => void
  onNext: () => void
}) {
  const fx = quote.market_feed?.fx
  const offers = quote.market_feed?.offers
  return (
    <div className="text-sm leading-6">
      <p className="font-medium">{quote.name} · {quote.sku}</p>
      <div className="mt-1 text-xs text-muted-foreground">竞争中位价<TermHint id="median" />，且不低于 15% 成本加成。汇率<TermHint id="fx" /> {fx?.used ? `Frankfurter ${fx.rate}` : fx?.rate || '商品汇率'}。货架价 {offers?.provider === 'global-pricer' ? '全球商品动态报价' : '本地报价本'}。</div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="inline-flex items-center">标价<TermHint id="listed" /> <span className="ml-1 font-semibold">${quote.listed_price_usd}</span></div>
        <div className="inline-flex items-center">建议<TermHint id="recommended" /> <span className="ml-1 font-semibold">${quote.recommended_price_usd}</span></div>
        <div className="inline-flex items-center">利润线<TermHint id="floor" /> <span className="ml-1 font-semibold">${quote.floor_price_usd}</span></div>
        <div className="inline-flex items-center">利润率<TermHint id="margin" /> <span className="ml-1 font-semibold">{percent(quote.report.profit.net_margin)}</span></div>
        <div className="inline-flex items-center">国内中位<TermHint id="median" /> {quote.domestic.median ? `¥${quote.domestic.median}` : '—'}</div>
        <div className="inline-flex items-center">{quote.overseas.market} 中位<TermHint id="median" /> {quote.overseas.median ? `$${quote.overseas.median}` : '—'}</div>
        <div className="inline-flex items-center">位置<TermHint id="position" /> {positionLabel[quote.position] || quote.position}</div>
        <div className="inline-flex items-center">风险<TermHint id="risk" /> {quote.report.risk.risk_level}</div>
      </div>
      <p className="mt-4">{quote.advice}</p>
      {total > 1 && (
        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <button type="button" className="rounded-lg border border-border px-2 py-1" onClick={onPrev} disabled={index === 0}>上一条</button>
          <span>{index + 1} / {total}</span>
          <button type="button" className="rounded-lg border border-border px-2 py-1" onClick={onNext} disabled={index === total - 1}>下一条</button>
        </div>
      )}
    </div>
  )
}

function Field({ label, hint, value, onChange }: { label: string; hint?: SelectionTermId; value: string; onChange: (value: string) => void }) {
  return (
    <label className="text-[11px] text-muted-foreground sm:text-xs"><span className="inline-flex items-center whitespace-nowrap">{label}{hint && <TermHint id={hint} />}</span>
      <input className="mt-0.5 h-8 w-full rounded-lg border-0 bg-muted px-2 text-sm text-foreground outline-none" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}
