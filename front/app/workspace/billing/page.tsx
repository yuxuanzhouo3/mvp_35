'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { readClient } from '@/lib/client-adapter'
import { ResultDesk } from '@/components/result-desk'
import { sharePlan } from '../acquire/share-plans'

type Plan = { id: string; name: string; amount_fen: number; period: string }
type JsapiPay = {
  appId: string
  timeStamp: string
  nonceStr: string
  package: string
  signType: string
  paySign: string
}
type Payment = {
  id: string
  amount: number
  status: string
  kind?: string
  plan_id?: string | null
  currency?: string
  code_url?: string | null
  pay_url?: string | null
  jsapi?: JsapiPay | null
  message?: string
}
type Invoice = { id: string; amount: number; status: string; payment_id?: string }
type Subscription = { id: string; status: string; plan_id?: string; plan?: string; period_end?: string }
type Summary = {
  plans: Plan[]
  payment_testing?: boolean
  subscription: { items: Subscription[] }
  payments: { items: Payment[] }
  invoices: { items: Invoice[] }
}

function yuan(fen: number) {
  return `¥${(fen / 100).toFixed(2)}`
}

function invokeMiniProgramPay(params: JsapiPay) {
  const host = window as Window & {
    wx?: { miniProgram?: { navigateTo?: (options: { url: string }) => void } }
    WeixinJSBridge?: { invoke: (name: string, payload: JsapiPay, callback: (result: { err_msg?: string }) => void) => void }
  }
  const query = new URLSearchParams({
    timeStamp: params.timeStamp,
    nonceStr: params.nonceStr,
    package: params.package,
    signType: params.signType,
    paySign: params.paySign,
  })
  if (host.wx?.miniProgram?.navigateTo) {
    host.wx.miniProgram.navigateTo({ url: `/pages/pay/index?${query.toString()}` })
    return
  }
  if (host.WeixinJSBridge) {
    host.WeixinJSBridge.invoke('getBrandWCPayRequest', params, () => undefined)
  }
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
  const [qr, setQr] = useState('')
  const [qrImage, setQrImage] = useState('')
  const [pickedPlan, setPickedPlan] = useState('')
  const [ordersOpen, setOrdersOpen] = useState(false)
  const [invoicesOpen, setInvoicesOpen] = useState(false)

  async function load() {
    const data = await api<Summary>('/billing/summary')
    setSummary(data)
  }

  useEffect(() => {
    setPickedPlan(new URLSearchParams(window.location.search).get('plan') || '')
    load().catch((reason: Error) => setError(reason.message))
  }, [])

  useEffect(() => {
    if (!qr) return
    let cancelled = false
    import('qrcode')
      .then((mod) => (mod.default ?? mod).toDataURL(qr, { margin: 1, width: 220 }))
      .then((url) => {
        if (!cancelled) setQrImage(url)
      })
      .catch(() => {
        if (!cancelled) setQrImage('')
      })
    return () => {
      cancelled = true
    }
  }, [qr])

  async function checkout(planId: string, provider: 'wechat' | 'alipay') {
    setBusy(true)
    setError('')
    setNotice('')
    setQr('')
    setQrImage('')
    const miniprogram = readClient()?.shell === 'miniprogram'
    try {
      const payment = await api<Payment>('/payments/checkout', {
        method: 'POST',
        body: JSON.stringify({
          plan_id: planId,
          kind: 'subscription',
          provider,
          scene: provider === 'wechat' && miniprogram ? 'miniprogram' : 'web',
          idempotency_key: `plan-${planId}-${provider}-${Date.now()}`,
        }),
      })
      if (payment.jsapi) {
        invokeMiniProgramPay(payment.jsapi)
        setNotice(`订单 ${payment.id} 已创建。请在微信小程序里确认支付，入账以后台签名回调为准。`)
      } else if (provider === 'wechat' && payment.code_url) {
        setQr(payment.code_url)
        setNotice(`订单 ${payment.id} 已创建。请用微信扫码支付，付完后点查询。入账以后台签名回调为准。`)
      } else if (provider === 'alipay' && payment.pay_url) {
        setNotice(`订单 ${payment.id} 已创建。请前往支付宝完成付款，入账以后台签名回调为准。`)
        window.open(payment.pay_url, '_blank', 'noopener,noreferrer')
      } else {
        setNotice(payment.message || `订单 ${payment.id} 保持待支付，尚未入账。`)
      }
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
  const picked = sharePlan(pickedPlan)
  const payments = summary?.payments.items || []
  const invoices = summary?.invoices.items || []
  const pendingCount = payments.filter((item) => item.status === 'pending').length

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="eyebrow">账单</span>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">套餐与支付</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">下单后是待支付。商户配置完整后才会给出付款地址。</p>
        {summary?.payment_testing && <p className="mt-2 text-sm text-muted-foreground">当前是支付测试，付费套餐实付 0.10 元。</p>}
        {picked && (
          <p className="mt-3 max-w-3xl rounded-xl border border-border bg-card px-4 py-3 text-sm leading-6">
            这一档是{picked.name}：成交和召回成交抽成 {Math.round(picked.take * 100)}%，已送达线索 ¥{(picked.leadFen / 100).toFixed(2)} / 条，已送达召回 ¥{(picked.recallFen / 100).toFixed(2)} / 次。
            {picked.monthYuan > 0 ? ` 月费 ¥${picked.monthYuan}。抽成要等这笔支付成功才换成新档，待支付仍按原档。` : ' 免费档不产生支付单。'}
            手点赢单和私下收款不进入抽成。
          </p>
        )}
        {!summary && !error && <p className="mt-4 text-sm text-muted-foreground">正在加载账单…</p>}
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {notice && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {qr && (
        <section className="flex max-w-sm flex-col items-start gap-3 rounded-2xl border border-border bg-card p-5">
          <h2 className="font-semibold">微信扫码支付</h2>
          {qrImage ? <img src={qrImage} alt="微信支付二维码" width={220} height={220} /> : <p className="text-sm text-muted-foreground">正在生成二维码…</p>}
          <p className="text-sm text-muted-foreground">用微信扫一扫。支付结果以签名回调为准，完成后点下方查询。</p>
        </section>
      )}
      <section className="grid gap-4 md:grid-cols-3">
        {picked && <h2 className="md:col-span-3 font-semibold">已接通的支付套餐</h2>}
        {(summary?.plans || []).map((plan) => (
          <article key={plan.id} className="soft-card p-5">
            <h2 className="font-semibold">{plan.name}</h2>
            <p className="mt-2 text-2xl font-semibold">{yuan(plan.amount_fen)}<span className="text-sm font-normal text-muted-foreground"> / {plan.period === 'year' ? '年' : '月'}</span></p>
            {plan.amount_fen > 0 ? (
              <div className="mt-4 flex gap-2">
                <button disabled={busy} className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" onClick={() => void checkout(plan.id, 'wechat')}>微信支付</button>
                <button disabled={busy} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-50" onClick={() => void checkout(plan.id, 'alipay')}>支付宝</button>
              </div>
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
      <section className="rounded-2xl border border-border bg-card p-5">
        <button type="button" className="flex w-full items-center justify-between gap-3 text-left" aria-expanded={ordersOpen} onClick={() => setOrdersOpen((open) => !open)}>
          <span>
            <span className="font-semibold">支付单</span>
            <span className="mt-1 block text-sm text-muted-foreground">{payments.length} 笔{pendingCount > 0 ? ` · 待支付 ${pendingCount}` : ''}</span>
          </span>
          <span className="text-sm text-primary">{ordersOpen ? '收起' : '展开'}</span>
        </button>
        {ordersOpen && (
          <div className="mt-4">
            <ResultDesk
              items={payments}
              placeholder="搜索支付单、套餐或状态"
              keywords={(payment) => `${payment.id} ${payment.plan_id || ''} ${payment.kind || ''} ${statusLabel[payment.status] || payment.status}`}
              filters={[{ key: 'status', label: '状态', value: (payment) => payment.status, labels: statusLabel }]}
              sorts={[
                { id: 'amount-desc', label: '金额高到低', compare: (left, right) => right.amount - left.amount },
                { id: 'amount-asc', label: '金额低到高', compare: (left, right) => left.amount - right.amount },
              ]}
              pageSize={5}
              empty="没有符合条件的支付单。"
              render={(payment) => (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{payment.id}</p>
                    <p className="text-xs text-muted-foreground">{payment.kind || 'subscription'} {payment.plan_id || ''}</p>
                  </div>
                  <p className="text-sm">{yuan(payment.amount)}</p>
                  <p className="text-sm">{statusLabel[payment.status] || payment.status}</p>
                  {payment.status === 'pending' && <button type="button" className="text-sm text-primary disabled:opacity-50" disabled={busy} onClick={() => void query(payment.id)}>查询</button>}
                </div>
              )}
            />
          </div>
        )}
      </section>
      <section className="rounded-2xl border border-border bg-card p-5">
        <button type="button" className="flex w-full items-center justify-between gap-3 text-left" aria-expanded={invoicesOpen} onClick={() => setInvoicesOpen((open) => !open)}>
          <span>
            <span className="font-semibold">发票</span>
            <span className="mt-1 block text-sm text-muted-foreground">{invoices.length > 0 ? `${invoices.length} 张` : '入账后才会开票'}</span>
          </span>
          <span className="text-sm text-primary">{invoicesOpen ? '收起' : '展开'}</span>
        </button>
        {invoicesOpen && (
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {invoices.map((invoice) => (
              <li key={invoice.id}>{invoice.id} · {yuan(invoice.amount)} · {statusLabel[invoice.status] || invoice.status}</li>
            ))}
            {summary && invoices.length === 0 && <li className="text-muted-foreground">入账后才会开票。</li>}
          </ul>
        )}
      </section>
    </div>
  )
}
