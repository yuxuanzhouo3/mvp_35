'use client'

import { useState } from 'react'
import { api, waitJob } from '@/lib/api'
import { ProductLibrary } from '@/components/product-library'

type CatalogItem = {
  id: string
  name: string
  sku: string
  category: string
  cost_cny: string
  target_price_usd: string
  supplier: string
}

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
  target_market: 'US',
  incoterm: 'DDP',
  tax_regime: 'cn_us',
  cost_currency: 'CNY',
  price_currency: 'USD',
  fx_usd_cny: '7.20',
  hs_code_hint: '',
}

export default function ProductsPage() {
  const [tab, setTab] = useState<'own' | 'catalog'>('own')
  const [form, setForm] = useState(emptyForm)
  const [csv, setCsv] = useState('sku,name,cost_cny,target_price_usd,international_freight_usd\nCUP-1,样品杯,72,40,2\n')
  const [csvFile, setCsvFile] = useState('')
  const [query, setQuery] = useState('杯')
  const [catalog, setCatalog] = useState<CatalogItem[]>([])
  const [libraryKey, setLibraryKey] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="eyebrow">路径 A · 选品与分析报告</span>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">双向入口，同一商品库</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">手动、CSV 或国内货源目录都会写入 products。默认货源中国、目标美国、中美税、成本人民币、售价美元。改市场后必须重新分析。</p>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {message && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</p>}
      <div className="flex gap-2">
        <button className={`rounded-lg px-3 py-1.5 text-sm ${tab === 'own' ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => setTab('own')}>自有导入</button>
        <button className={`rounded-lg px-3 py-1.5 text-sm ${tab === 'catalog' ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => setTab('catalog')}>帮我选品</button>
      </div>
      {tab === 'own' ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <form className="rounded-2xl border border-border bg-card p-5" onSubmit={(event) => {
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
              <label className="text-xs text-muted-foreground">目标市场
                <select className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-2 text-sm text-foreground" value={form.target_market} onChange={(event) => {
                  const market = event.target.value
                  const regime = market === 'AU' ? 'cn_au' : market === 'HK' ? 'cn_hk' : market === 'CN' ? 'domestic' : 'cn_us'
                  setForm((current) => ({ ...current, target_market: market, tax_regime: regime }))
                }}>
                  <option value="US">美国</option>
                  <option value="HK">香港</option>
                  <option value="AU">澳大利亚</option>
                  <option value="CN">内陆</option>
                </select>
              </label>
              <Field label="贸易术语" value={form.incoterm} onChange={(value) => setField('incoterm', value)} />
            </div>
            <button disabled={busy} className="mt-4 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50">写入商品库</button>
          </form>
          <form className="rounded-2xl border border-border bg-card p-5" onSubmit={(event) => {
            event.preventDefault()
            void run(async () => {
              const created = await api<{ job_id: string }>('/products/imports', { method: 'POST', body: JSON.stringify({ csv, algorithm: 'product-pricer' }) })
              const job = await waitJob(created.job_id)
              if (job.status === 'failed') throw new Error(job.error?.message || '导入失败')
              setMessage(`CSV 导入完成：成功 ${job.result?.imported ?? 0}，失败 ${job.result?.failed ?? 0}。`)
            })
          }}>
            <h2 className="font-semibold">CSV 导入</h2>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">表头至少包含 sku、name、cost_cny、target_price_usd。可以粘贴，也可以上传文件。任务返回 202，由 worker 入库。</p>
            <textarea className="mt-3 h-40 w-full rounded-xl border border-border bg-background p-3 font-mono text-xs" value={csv} onChange={(event) => setCsv(event.target.value)} />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="inline-flex min-h-9 cursor-pointer items-center rounded-lg border border-border px-3 text-sm">
                上传文件
                <input
                  type="file"
                  accept=".csv,text/csv,text/plain"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (!file) return
                    setCsvFile(file.name)
                    file.text().then((text) => setCsv(text)).catch(() => setError('无法读取这个文件'))
                  }}
                />
              </label>
              <button disabled={busy} className="min-h-9 rounded-lg bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50">开始导入</button>
              {csvFile && <span className="text-xs text-muted-foreground">{csvFile}</span>}
            </div>
            <AlgorithmHold
              title="国内外商品定价"
              algorithm="product-pricer"
              copy="这里只留给即将接入的定价算法和国内外商品 pricer API。导入只提交这一路，不带选品算法。"
            />
          </form>
        </div>
      ) : (
        <div className="rounded-2xl border border-border bg-card p-5">
          <h2 className="font-semibold">国内货源目录</h2>
          <p className="mt-2 text-xs text-muted-foreground">当前是演示目录。选品算法和外部货源 API 还在占位，搜索只带这一路。</p>
          <AlgorithmHold
            title="帮我选品"
            algorithm="selection-assist"
            copy="这里只留给即将接入的选品算法和货源 API。搜索只提交这一路，不带定价接口。"
          />
          <div className="mt-3 flex gap-2">
            <input className="w-full max-w-xs rounded-lg border border-border px-3 py-2 text-sm" value={query} onChange={(event) => setQuery(event.target.value)} aria-label="搜索货源" />
            <button className="inline-flex min-h-9 shrink-0 items-center whitespace-nowrap rounded-lg border border-border px-3 text-sm" onClick={() => {
              void run(async () => {
                const data = await api<{ items: CatalogItem[] }>(`/catalog/search?q=${encodeURIComponent(query)}&algorithm=selection-assist`)
                setCatalog(data.items)
              })
            }}>搜索</button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {catalog.map((item) => (
              <article key={item.id} className="rounded-xl border border-border p-3">
                <h3 className="font-medium">{item.name}</h3>
                <p className="mt-1 text-xs text-muted-foreground">{item.supplier} · {item.sku}</p>
                <p className="mt-2 text-sm">成本 ¥{item.cost_cny} · 参考售价 ${item.target_price_usd}</p>
                <button disabled={busy} className="mt-3 text-sm text-primary" onClick={() => {
                  void run(async () => {
                    await api('/catalog/adopt', { method: 'POST', body: JSON.stringify({ catalog_id: item.id }) })
                    setMessage(`${item.name} 已进入商品库。`)
                  })
                }}>入库</button>
              </article>
            ))}
          </div>
        </div>
      )}
      <div>
        <h2 className="text-lg font-semibold">已入库商品</h2>
        <p className="mt-1 text-sm text-muted-foreground">搜索名称或 SKU，使用会生成分析报告，删除后这条记录不再出现。</p>
        <div className="mt-4">
          <ProductLibrary key={libraryKey} />
        </div>
      </div>
    </div>
  )
}

function AlgorithmHold({ title, algorithm, copy }: { title: string; algorithm: string; copy: string }) {
  return (
    <div className="mt-4 rounded-xl border border-dashed border-primary/40 bg-primary/5 p-4">
      <p className="text-xs font-semibold text-primary">算法占位</p>
      <p className="mt-1 text-sm font-medium">{title}</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">{copy}</p>
      <p className="mt-2 font-mono text-[11px] text-muted-foreground">即将接入 · {algorithm}</p>
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
