'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api, waitJob } from '@/lib/api'

type Product = {
  id: string
  name: string
  sku: string
  origin_country?: string
  target_market?: string
  target_price_usd?: string
}

export function ProductLibrary() {
  const router = useRouter()
  const [q, setQ] = useState('')
  const [items, setItems] = useState<Product[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

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
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault()
          void run(async () => {
            await load(q)
          })
        }}
      >
        <input
          className="min-h-12 w-full rounded-xl border border-border bg-background px-3 text-base"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="按名称或 SKU 搜索"
          aria-label="搜索商品"
        />
        <button disabled={busy} className="min-h-12 rounded-xl bg-primary px-5 text-base text-primary-foreground disabled:opacity-50">
          搜索
        </button>
      </form>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {message && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</p>}
      <div className="grid gap-3">
        {items.map((product) => (
          <article key={product.id} className="rounded-2xl border border-border bg-card p-4">
            <h3 className="text-base font-semibold">{product.name}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {product.sku}
              {product.origin_country && product.target_market ? ` · ${product.origin_country} → ${product.target_market}` : ''}
              {product.target_price_usd ? ` · $${product.target_price_usd}` : ''}
            </p>
            <div className="mt-3 flex gap-2">
              <button
                disabled={busy}
                className="min-h-12 flex-1 rounded-xl bg-primary px-3 text-base text-primary-foreground disabled:opacity-50"
                onClick={() => {
                  void run(async () => {
                    const created = await api<{ job_id: string }>(`/products/${product.id}/analyses`, { method: 'POST' })
                    const job = await waitJob(created.job_id)
                    if (job.status === 'failed' || !job.result?.analysis_id) throw new Error(job.error?.message || '分析失败')
                    router.push(`/workspace/reports/${job.result.analysis_id}`)
                  })
                }}
              >
                使用
              </button>
              <button
                disabled={busy}
                className="min-h-12 rounded-xl border border-border px-4 text-base disabled:opacity-50"
                onClick={() => {
                  if (!window.confirm(`删除「${product.name}」？删除后搜索不到这条商品。`)) return
                  void run(async () => {
                    await api(`/products/${product.id}`, { method: 'DELETE' })
                    setMessage(`已删除 ${product.name}`)
                    await load(q)
                  })
                }}
              >
                删除
              </button>
            </div>
          </article>
        ))}
        {items.length === 0 && <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">没有匹配的商品。</p>}
      </div>
    </div>
  )
}
