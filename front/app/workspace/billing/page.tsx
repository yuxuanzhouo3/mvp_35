'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

type Plan = { id: string; name: string; amount_fen: number; period: string }
type Payment = { id: string; amount: number; status: string; kind?: string; plan_id?: string | null; currency?: string }
type Invoice = { id: string; amount: number; status: string; payment_id?: string }
type Subscription = { id: string; status: string; plan_id?: string; plan?: string; period_end?: string }
type Summary = {
  plans: Plan[]
  subscription: { items: Subscription[] }
  payments: { items: Payment[] }
  invoices: { items: Invoice[] }
}

function yuan(fen: number) {
  return `¥${(fen / 100).toFixed(2)}`
}

const statusLabel: Record<string, string> = {
  pending: '待支付',
  succeeded: '已入账',
  failed: '失败',
  refunded: '已退款',
  active: '生效中',
  issued: '已开票',
  created: '已创建',
}

export default function BillingPage() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    const data = await api<Summary>('/billing/summary')
    setSummary(data)
  }

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message))
  }, [])

  async function checkout(planId: string) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const payment = await api<Payment>('/payments/checkout', {
        method: 'POST',
        body: JSON.stringify({ plan_id: planId, kind: 'subscription', idempotency_key: `plan-${planId}-${Date.now()}` }),
      })
      setNotice(`订单 ${payment.id} 已创建，状态为${statusLabel[payment.status] || payment.status}。页面不会伪造支付成功，入账以后台签名回调为准。`)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '下单失败')
    } finally {
      setBusy(false)
    }
  }

  async function query(paymentId: string) {
    setBusy(true)
    setError('')
    try {
      const payment = await api<{ status: string; granted: boolean }>(`/payments/${paymentId}/query`, { method: 'POST' })
      setNotice(payment.granted ? '这笔支付已入账。' : `查询结果仍是${statusLabel[payment.status] || payment.status}，尚未入账。`)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '查询失败')
    } finally {
      setBusy(false)
    }
  }

  const active = summary?.subscription.items.find((item) => item.status === 'active')

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="eyebrow">账单</span>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">套餐与支付</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">下单后状态是待支付。微信收款未接通。浏览器不调用支付回调，也不把待支付显示成成功。</p>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {notice && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      <section className="grid gap-4 md:grid-cols-3">
        {(summary?.plans || []).map((plan) => (
          <article key={plan.id} className="rounded-2xl border border-border bg-card p-5">
            <h2 className="font-semibold">{plan.name}</h2>
            <p className="mt-2 text-2xl font-semibold">{yuan(plan.amount_fen)}<span className="text-sm font-normal text-muted-foreground"> / {plan.period === 'year' ? '年' : '月'}</span></p>
            {plan.amount_fen > 0 ? (
              <button disabled={busy} className="mt-4 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" onClick={() => void checkout(plan.id)}>下单</button>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">当前默认套餐</p>
            )}
          </article>
        ))}
      </section>
      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="font-semibold">订阅</h2>
        <p className="mt-2 text-sm text-muted-foreground">{active ? `${active.plan_id || active.plan} · ${statusLabel[active.status] || active.status}` : '还没有生效中的付费订阅。'}</p>
      </section>
      <section className="overflow-hidden rounded-2xl border border-border bg-card">
        <table className="data-table">
          <thead><tr><th>支付单</th><th>金额</th><th>状态</th><th></th></tr></thead>
          <tbody>
            {(summary?.payments.items || []).map((payment) => (
              <tr key={payment.id}>
                <td>{payment.id}<div className="text-xs text-muted-foreground">{payment.kind || 'subscription'} {payment.plan_id || ''}</div></td>
                <td>{yuan(payment.amount)}</td>
                <td>{statusLabel[payment.status] || payment.status}</td>
                <td>{payment.status === 'pending' && <button className="text-sm text-primary" disabled={busy} onClick={() => void query(payment.id)}>查询</button>}</td>
              </tr>
            ))}
            {summary && summary.payments.items.length === 0 && <tr><td colSpan={4} className="text-muted-foreground">还没有支付单。</td></tr>}
          </tbody>
        </table>
      </section>
      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="font-semibold">发票</h2>
        <ul className="mt-3 flex flex-col gap-2 text-sm">
          {(summary?.invoices.items || []).map((invoice) => (
            <li key={invoice.id}>{invoice.id} · {yuan(invoice.amount)} · {statusLabel[invoice.status] || invoice.status}</li>
          ))}
          {summary && summary.invoices.items.length === 0 && <li className="text-muted-foreground">入账后才会开票。</li>}
        </ul>
      </section>
    </div>
  )
}
