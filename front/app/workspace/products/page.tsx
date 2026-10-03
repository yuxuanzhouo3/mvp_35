'use client'

import { useState } from 'react'
import { api, percent, waitJob } from '@/lib/api'
import { ProductLibrary } from '@/components/product-library'
import { ReportDialog } from '@/components/report-dialog'
import { ResultDesk } from '@/components/result-desk'

type Selection = {
  pick: boolean
  score: number
  net_margin: string
  risk_level: string
  reason: string
}

type CatalogItem = {
  id: string
  name: string
  sku: string
  category: string
  cost_cny: string
  target_price_usd: string
  supplier: string
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

const routes = {
  domestic: { origin_country: 'CN', target_market: 'CN', tax_regime: 'domestic', route: 'CN-CN', label: '国内' },
  cn_us: { origin_country: 'CN', target_market: 'US', tax_regime: 'cn_us', route: 'CN-US', label: '中国 → 美国' },
  cn_hk: { origin_country: 'CN', target_market: 'HK', tax_regime: 'cn_hk', route: 'CN-HK', label: '中国 → 香港' },
  cn_au: { origin_country: 'CN', target_market: 'AU', tax_regime: 'cn_au', route: 'CN-AU', label: '中国 → 澳大利亚' },
  us_cn: { origin_country: 'US', target_market: 'CN', tax_regime: 'domestic', route: 'US-CN', label: '美国 → 中国' },
} as const

type RouteId = keyof typeof routes

const emptyForm = {
  name: '',
  sku: '',
  category: '家居',
  cost_cny: '72',
  packaging_cny: '4',
  domestic_freight_cny: '6',
  international_freight_usd: '3.2',
  target_price_usd: '39',
  origin_country: 'CN',
  target_market: 'CN',
  route: 'CN-CN',
  incoterm: 'DDP',
  tax_regime: 'domestic',
  cost_currency: 'CNY',
  price_currency: 'USD',
  fx_usd_cny: '7.20',
  hs_code_hint: '',
}

function routeId(form: { origin_country: string; target_market: string }): RouteId {
  if (form.origin_country === 'US' && form.target_market === 'CN') return 'us_cn'
  if (form.target_market === 'HK') return 'cn_hk'
  if (form.target_market === 'AU') return 'cn_au'
  if (form.target_market === 'US') return 'cn_us'
  return 'domestic'
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
  const [tab, setTab] = useState<'manual' | 'sheet' | 'catalog' | 'library'>('manual')
  const [form, setForm] = useState(emptyForm)
  const [csv, setCsv] = useState('sku,name,cost_cny,target_price_usd,international_freight_usd\nCUP-1,样品杯,72,40,2\n')
  const [csvFile, setCsvFile] = useState('')
  const [catalog, setCatalog] = useState<CatalogItem[]>([])
  const [libraryKey, setLibraryKey] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [quotes, setQuotes] = useState<Quote[]>([])
  const [quoteOpen, setQuoteOpen] = useState(false)
  const [quoteIndex, setQuoteIndex] = useState(0)

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
    { id: 'manual', name: '手动录入' },
    { id: 'sheet', name: '表格导入' },
    { id: 'catalog', name: '帮我选品' },
    { id: 'library', name: '已入库' },
  ] as const

  return (
    <div className="flex h-[calc(100dvh-11rem)] flex-col gap-3 overflow-hidden md:h-[calc(100dvh-9rem)]">
      <div className="shrink-0">
        <span className="eyebrow">路径 A · 选品与分析报告</span>
        <h1 className="text-2xl font-semibold tracking-tight">双向入口，同一商品库</h1>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">四个功能在这一屏切换。表格支持 CSV、TSV 和 Excel。改市场后必须重新分析。</p>
      </div>
      {error && <p className="shrink-0 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      {message && <p className="shrink-0 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p>}
      <div className="grid shrink-0 grid-cols-2 gap-2 lg:grid-cols-4">
        {views.map((item) => (
          <button key={item.id} type="button" className={`h-11 rounded-xl px-2 text-sm font-medium ${tab === item.id ? 'bg-primary text-primary-foreground' : 'border border-border bg-card'}`} onClick={() => setTab(item.id)}>
            {item.name}
          </button>
        ))}
      </div>
      <section className="min-h-0 flex-1 overflow-y-auto rounded-3xl border border-border bg-card p-4 md:p-5">
      {tab === 'manual' ? (
          <form onSubmit={(event) => {
            event.preventDefault()
            void run(async () => {
              await api('/products', { method: 'POST', body: JSON.stringify(form) })
              setMessage('商品已入库，可以开始分析。')
            })
          }}>
            <h2 className="font-semibold">手动录入</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Field label="名称" value={form.name} onChange={(value) => setField('name', value)} />
              <Field label="SKU" value={form.sku} onChange={(value) => setField('sku', value)} />
              <Field label="采购成本 CNY" value={form.cost_cny} onChange={(value) => setField('cost_cny', value)} />
              <Field label="售价 USD" value={form.target_price_usd} onChange={(value) => setField('target_price_usd', value)} />
              <Field label="包装 CNY" value={form.packaging_cny} onChange={(value) => setField('packaging_cny', value)} />
              <Field label="国内段 CNY" value={form.domestic_freight_cny} onChange={(value) => setField('domestic_freight_cny', value)} />
              <Field label="国际段 USD" value={form.international_freight_usd} onChange={(value) => setField('international_freight_usd', value)} />
              <Field label="汇率 USD/CNY" value={form.fx_usd_cny} onChange={(value) => setField('fx_usd_cny', value)} />
              <label className="text-xs text-muted-foreground">路线
                <select className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-2 text-sm text-foreground" value={routeId(form)} onChange={(event) => {
                  const next = routes[event.target.value as RouteId]
                  setForm((current) => ({
                    ...current,
                    origin_country: next.origin_country,
                    target_market: next.target_market,
                    tax_regime: next.tax_regime,
                    route: next.route,
                  }))
                }}>
                  {(Object.keys(routes) as RouteId[]).map((id) => (
                    <option key={id} value={id}>{routes[id].label}</option>
                  ))}
                </select>
              </label>
              <Field label="贸易术语" value={form.incoterm} onChange={(value) => setField('incoterm', value)} />
            </div>
            <button disabled={busy} className="mt-4 h-11 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50">写入商品库</button>
          </form>
      ) : tab === 'sheet' ? (
          <form onSubmit={(event) => {
            event.preventDefault()
            void run(async () => {
              const created = await api<{ job_id: string }>('/products/imports', { method: 'POST', body: JSON.stringify({ csv, algorithm: 'product-pricer' }) })
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
            <h2 className="font-semibold">表格导入</h2>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">表头至少包含 sku、name、cost_cny、target_price_usd。可粘贴 CSV，或上传 CSV、TSV、Excel（.xlsx / .xls）。任务返回 202，由 worker 入库。</p>
            <textarea className="mt-3 h-40 w-full rounded-xl border border-border bg-background p-3 font-mono text-xs" value={csv} onChange={(event) => setCsv(event.target.value)} />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="inline-flex min-h-9 cursor-pointer items-center rounded-lg border border-border px-3 text-sm">
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
              <button disabled={busy} className="min-h-9 rounded-lg bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50">开始导入</button>
              {csvFile && <span className="text-xs text-muted-foreground">{csvFile}</span>}
            </div>
            <div className="mt-4 rounded-xl border border-primary/30 bg-primary/5 p-4">
              <p className="text-xs font-semibold text-primary">算法</p>
              <p className="mt-1 text-sm font-medium">国内外商品定价</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">比价对照货架价给出建议售价，不低于 15% 利润线。先比价不入库。</p>
            </div>
            <button
              type="button"
              disabled={busy}
              className="mt-3 min-h-9 rounded-lg border border-border px-3 text-sm disabled:opacity-50"
              onClick={() => {
                void run(async () => {
                  const priced = await api<{ items: Quote[] }>('/algorithms/product-pricer', { method: 'POST', body: JSON.stringify({ csv }) })
                  setQuotes(priced.items)
                  setQuoteIndex(0)
                  setQuoteOpen(priced.items.length > 0)
                  setMessage(priced.items.length ? `已比对 ${priced.items.length} 条售价。` : '没有可比对的商品行。')
                })
              }}
            >先比价，不入库</button>
            {quotes.length > 0 && (
              <button type="button" className="mt-3 text-sm text-primary" onClick={() => setQuoteOpen(true)}>
                阅读利润报告（{quotes.length}）
              </button>
            )}
          </form>
      ) : tab === 'catalog' ? (
        <div>
          <h2 className="font-semibold">国内货源目录</h2>
          <p className="mt-1 text-sm text-muted-foreground">搜索只带选品排序。利润率达到 15% 且风险不是高的商品优先。</p>
          <div className="mt-3">
            <ResultDesk
              items={catalog}
              placeholder="搜索名称、SKU 或供应商"
              keywords={(item) => `${item.name} ${item.sku} ${item.supplier} ${item.category}`}
              onSearch={(next) => {
                void run(async () => {
                  const data = await api<{ items: CatalogItem[] }>(`/catalog/search?q=${encodeURIComponent(next)}&algorithm=selection-assist`)
                  setCatalog(data.items)
                })
              }}
              filters={[{ key: 'pick', label: '建议', value: (item) => item.selection?.pick ? '优先' : '暂缓' }]}
              sorts={[
                { id: 'score', label: '机会分', compare: (left, right) => (right.selection?.score || 0) - (left.selection?.score || 0) },
                { id: 'margin', label: '利润率', compare: (left, right) => (right.selection?.net_margin || '').localeCompare(left.selection?.net_margin || '') },
                { id: 'name', label: '名称', compare: (left, right) => left.name.localeCompare(right.name, 'zh') },
              ]}
              empty="还没有货源结果。输入关键词后搜索。"
              render={(item) => (
                <article className="rounded-xl border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="font-medium">{item.name}</h3>
                      <p className="mt-1 text-xs text-muted-foreground">{item.supplier} · {item.sku} · ¥{item.cost_cny} · ${item.target_price_usd}</p>
                      {item.selection && <p className="mt-1 text-xs text-muted-foreground">{item.selection.pick ? '优先' : '暂缓'} · 机会分 {item.selection.score} · 利润率 {item.selection.net_margin} · 风险 {item.selection.risk_level}</p>}
                    </div>
                    <button type="button" disabled={busy} className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => {
                      void run(async () => {
                        await api('/catalog/adopt', { method: 'POST', body: JSON.stringify({ catalog_id: item.id }) })
                        setMessage(`${item.name} 已进入商品库。`)
                      })
                    }}>入库</button>
                  </div>
                </article>
              )}
            />
          </div>
        </div>
      ) : (
        <div>
          <h2 className="font-semibold">已入库商品</h2>
          <p className="mt-1 text-sm text-muted-foreground">按名称或 SKU 搜索。使用会生成分析报告。</p>
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
      <p className="mt-1 text-xs text-muted-foreground">竞争中位价，且不低于 15% 成本加成。汇率 {fx?.used ? `Frankfurter ${fx.rate}` : fx?.rate || '商品汇率'}。货架价 {offers?.provider === 'global-pricer' ? '全球商品动态报价' : '本地报价本'}。</p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <p>标价 <span className="font-semibold">${quote.listed_price_usd}</span></p>
        <p>建议 <span className="font-semibold">${quote.recommended_price_usd}</span></p>
        <p>利润线 <span className="font-semibold">${quote.floor_price_usd}</span></p>
        <p>利润率 <span className="font-semibold">{percent(quote.report.profit.net_margin)}</span></p>
        <p>国内中位 {quote.domestic.median ? `¥${quote.domestic.median}` : '—'}</p>
        <p>{quote.overseas.market} 中位 {quote.overseas.median ? `$${quote.overseas.median}` : '—'}</p>
        <p>位置 {positionLabel[quote.position] || quote.position}</p>
        <p>风险 {quote.report.risk.risk_level}</p>
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

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="text-xs text-muted-foreground">{label}
      <input className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-2 text-sm text-foreground" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}
