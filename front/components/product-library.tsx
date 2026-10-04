'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { api, waitJob } from '@/lib/api'
import { ResultDesk } from '@/components/result-desk'
import { TermHint } from '@/components/term-hint'
import { DEFAULT_ROUTE, placeName, readTradeRoute, TRADE_ROUTES, type RouteId } from '@/lib/trade-route'

type Product = {
  id: string
  name: string
  sku: string
  origin_country?: string
  target_market?: string
  target_price_usd?: string
  created_at?: string
}

export function ProductLibrary() {
  const router = useRouter()
  const pathname = usePathname()
  const [q, setQ] = useState('')
  const [items, setItems] = useState<Product[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const [route, setRoute] = useState<RouteId>(DEFAULT_ROUTE)

  useEffect(() => {
    function sync() {
      setRoute(readTradeRoute())
    }
    sync()
    window.addEventListener('pickglobal-route', sync)
    return () => window.removeEventListener('pickglobal-route', sync)
  }, [])

  async function load(next = q) {
    const data = await api<{ items: Product[] }>(`/products?q=${encodeURIComponent(next)}`)
    setItems(data.items)
  }

  useEffect(() => {
    load('').catch((reason: Error) => setError(reason.message))
  }, [])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await action()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '操作失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error === '需要登录' ? (
        <Link href={`/login?next=${encodeURIComponent(pathname || '/')}`} className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive underline">
          需要登录
        </Link>
      ) : error ? (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>
      ) : null}
      {message && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</p>}
      <ResultDesk
        items={items.filter((product) => !product.target_market || product.target_market === TRADE_ROUTES[route].target_market)}
        placeholder="按名称或 SKU 搜索"
        keywords={(product) => `${product.name} ${product.sku} ${product.origin_country || ''} ${product.target_market || ''}`}
        onSearch={(next) => {
          setQ(next)
          void run(async () => {
            await load(next)
          })
        }}
        filters={[{ key: 'market', label: '目标市场', value: (product) => product.target_market || '' }]}
        sorts={[
          { id: 'new', label: '时间新到旧', compare: (left, right) => (right.created_at || '').localeCompare(left.created_at || '') },
          { id: 'old', label: '时间旧到新', compare: (left, right) => (left.created_at || '').localeCompare(right.created_at || '') },
          { id: 'name', label: '名称', compare: (left, right) => left.name.localeCompare(right.name, 'zh') },
        ]}
        empty="没有匹配的商品。"
        render={(product) => (
          <article className="rounded-2xl border border-border bg-card p-4">
            <h3 className="text-base font-semibold">{product.name}</h3>
            <div className="mt-1 text-sm text-muted-foreground">
              <span className="inline-flex items-center">SKU {product.sku}<TermHint id="sku" /></span>
              {product.origin_country && product.target_market ? <span className="inline-flex items-center"> · {placeName(product.origin_country)} → {placeName(product.target_market)}<TermHint id="route" /></span> : ''}
              {product.target_price_usd ? <span className="inline-flex items-center"> · ${product.target_price_usd}<TermHint id="price" /></span> : ''}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                disabled={busy}
                className="min-h-12 flex-1 rounded-xl bg-primary px-3 text-base text-primary-foreground disabled:opacity-50"
                onClick={() => {
                  void run(async () => {
                    const created = await api<{ job_id: string }>(`/products/${product.id}/analyses`, { method: 'POST', body: JSON.stringify({ route }) })
                    const job = await waitJob(created.job_id)
                    if (job.status === 'failed' || !job.result?.analysis_id) throw new Error(job.error?.message || '分析失败')
                    router.push(`/workspace/reports/${job.result.analysis_id}`)
                  })
                }}
              >
                分析
              </button>
              <TermHint id="analyze" />
              <button
                disabled={busy}
                className="min-h-12 rounded-xl border border-border px-4 text-base disabled:opacity-50"
                onClick={() => {
                  if (pendingDelete !== product.id) {
                    setPendingDelete(product.id)
                    return
                  }
                  void run(async () => {
                    await api(`/products/${product.id}`, { method: 'DELETE' })
                    setPendingDelete(null)
                    setMessage(`已删除 ${product.name}`)
                    await load(q)
                  })
                }}
              >
                {pendingDelete === product.id ? '确认删除' : '删除'}
              </button>
            </div>
          </article>
        )}
      />
    </div>
  )
}
