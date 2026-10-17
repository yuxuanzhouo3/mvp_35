'use client'

import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { api } from '@/lib/api'
import { payTint } from '@/lib/brand-tints'
import { isPhoneClient, openExternalPay, openWechatPay } from '@/lib/device'
import { readClient } from '@/lib/client-adapter'
import { PayBrandMark } from '@/components/pay-brand-mark'
import { ResultDesk } from '@/components/result-desk'
import { sharePlan } from '../acquire/share-plans'

type Plan = { id: string; name: string; amount_fen: number; list_fen?: number; period: string; features?: string[]; tier?: string }
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

function listedFen(plan: Plan) {
  return plan.list_fen ?? plan.amount_fen
}

const tiers = ['free', 'growth', 'scale'] as const

const tierCopy: Record<(typeof tiers)[number], { blurb: string; features: string[] }> = {
  free: {
    blurb: '先试用选品和获客',
    features: ['分析 50 · 发现 50 · 发送 100', '货价每小时更新', '选品最多 5 条'],
  },
  growth: {
    blurb: '适合正在出单的卖家',
    features: ['分析 500 · 发现 500 · 发送 2,000', '货价每 15 分钟，另有 10 次刷新', '选品 10 条 · AI 每天 5 次'],
  },
  scale: {
    blurb: '适合要更高额度的团队',
    features: ['分析 5,000 · 发现 5,000 · 发送 20,000', '含专业版的货价刷新', '选品 30 条 · AI 每天 20 次'],
  },
}

function tierOf(plan: Plan) {
  if (plan.tier === 'free' || plan.tier === 'growth' || plan.tier === 'scale') return plan.tier
  const raw = plan.id.endsWith('_year') ? plan.id.slice(0, -5) : plan.id
  return raw === 'growth' || raw === 'scale' ? raw : 'free'
}

function planFor(plans: Plan[], tier: (typeof tiers)[number], cycle: 'month' | 'year') {
  if (tier === 'free') return plans.find((plan) => tierOf(plan) === 'free' && plan.period !== 'year')
  const id = cycle === 'year' ? `${tier}_year` : tier
  return plans.find((plan) => plan.id === id) || plans.find((plan) => tierOf(plan) === tier && plan.period === cycle)
}

function subscribedName(plans: Plan[], planId?: string) {
  const plan = plans.find((item) => item.id === planId)
  if (!plan) return planId || '付费套餐'
  if (plan.period === 'year') return `${plan.name} · 年付`
  if ((plan.list_fen ?? plan.amount_fen) > 0) return `${plan.name} · 月付`
  return plan.name
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
  const [cycle, setCycle] = useState<'month' | 'year'>('month')
  const [tier, setTier] = useState<(typeof tiers)[number]>('growth')
  const [provider, setProvider] = useState<'wechat' | 'alipay'>('wechat')

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
    const phone = isPhoneClient()
    try {
      const payment = await api<Payment>('/payments/checkout', {
        method: 'POST',
        body: JSON.stringify({
          plan_id: planId,
          kind: 'subscription',
          provider,
          scene: provider === 'wechat' && miniprogram ? 'miniprogram' : phone && (provider === 'wechat' || provider === 'alipay') ? 'wap' : 'web',
          idempotency_key: `plan-${planId}-${provider}-${Date.now()}`,
        }),
      })
      if (payment.jsapi) {
        invokeMiniProgramPay(payment.jsapi)
        setNotice(`订单 ${payment.id} 已创建。请在微信小程序里确认支付，入账以后台签名回调为准。`)
      } else if (provider === 'wechat' && phone && payment.pay_url) {
        setNotice(`订单 ${payment.id} 已创建。正在打开微信付款…付完后回此页点查询。`)
        openWechatPay(payment.pay_url)
      } else if (provider === 'wechat' && payment.code_url) {
        setQr(payment.code_url)
        setNotice(`订单 ${payment.id} 已创建。请用微信扫码，或点二维码打开微信付款。入账以后台签名回调为准。`)
      } else if (provider === 'alipay' && payment.pay_url) {
        setNotice(`订单 ${payment.id} 已创建。请前往支付宝完成付款，入账以后台签名回调为准。`)
        openExternalPay(payment.pay_url)
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
    <div className="flex flex-col gap-4">
      <div>
        <span className="eyebrow">订阅</span>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">订阅与支付</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">下单后是待支付。商户配置完整后才会给出付款地址。</p>
        {summary?.payment_testing && <p className="mt-2 text-sm text-muted-foreground">当前是支付测试，付费订阅实付 0.10 元。</p>}
        {picked && (
          <p className="mt-3 max-w-3xl rounded-xl border border-border bg-card px-4 py-3 text-sm leading-6">
            这一档是{picked.name}：成交和召回成交抽成 {Math.round(picked.take * 100)}%，已送达线索 ¥{(picked.leadFen / 100).toFixed(2)} / 条，已送达召回 ¥{(picked.recallFen / 100).toFixed(2)} / 次。
            {picked.monthYuan > 0 ? ` 月费 ¥${picked.monthYuan}。抽成要等这笔支付成功才换成新档，待支付仍按原档。` : ' 免费档不产生支付单。'}
            手点赢单和私下收款不进入抽成。
          </p>
        )}
        {!summary && !error && <p className="mt-4 text-sm text-muted-foreground">正在加载订阅…</p>}
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {notice && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      <section className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-2 pt-1">
          <button type="button" className={`h-9 min-w-[5.5rem] flex-1 rounded-full border text-sm sm:h-8 sm:flex-none sm:w-24 ${cycle === 'month' ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-foreground'}`} onClick={() => setCycle('month')}>月付</button>
          <button type="button" className={`relative h-9 min-w-[5.5rem] flex-1 rounded-full border text-sm sm:h-8 sm:flex-none sm:w-24 ${cycle === 'year' ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-foreground'}`} onClick={() => setCycle('year')}>
            年付
            <span className="absolute -right-1 -top-2 rounded-full bg-emerald-500 px-1.5 py-0.5 text-[10px] leading-none text-white sm:-right-2">省 30%</span>
          </button>
        </div>
        <div className="grid grid-cols-1 items-stretch gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {tiers.map((item) => {
            const plan = planFor(summary?.plans || [], item, cycle)
            const copy = tierCopy[item]
            const selected = tier === item
            const listed = plan ? listedFen(plan) : 0
            const perMonth = cycle === 'year' && item !== 'free' ? Math.round(listed / 12) : listed
            return (
              <article key={item} className={`soft-card relative flex h-full flex-col p-3 ${selected ? 'is-focus ring-2 ring-primary/25' : ''}`}>
                {item === 'growth' && <span className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full bg-primary px-2 py-0.5 text-[10px] text-primary-foreground">最受欢迎</span>}
                <h2 className="text-center text-sm font-semibold">{plan?.name || copy.blurb}</h2>
                <p className="mt-0.5 text-center text-[11px] text-muted-foreground">{copy.blurb}</p>
                <p className="mt-2 text-center text-2xl font-bold leading-none text-primary">{yuan(perMonth)}<span className="text-xs font-normal text-muted-foreground"> / 月</span></p>
                {cycle === 'year' && item !== 'free' && <p className="mt-1 text-center text-[11px] text-emerald-600">{yuan(listed)} / 年</p>}
                <ul className="mt-2 flex flex-1 flex-col gap-1">
                  {copy.features.map((line) => (
                    <li key={line} className="flex items-start gap-1.5 text-[11px] leading-4 text-muted-foreground">
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
                <button type="button" className={`mt-3 h-8 rounded-full text-sm ${selected ? 'bg-primary text-primary-foreground' : 'border border-border bg-secondary text-secondary-foreground'}`} onClick={() => setTier(item)}>
                  {item === 'free' ? '当前默认' : '选择此套餐'}
                </button>
              </article>
            )
          })}
          <aside className="soft-card flex h-full flex-col p-3">
            <h2 className="text-center text-sm font-semibold leading-5">{tier === 'free' ? '免费体验' : `完成${planFor(summary?.plans || [], tier, cycle)?.name || ''}购买`}</h2>
            {tier === 'free' ? (
              <p className="mt-auto pt-2 text-center text-[11px] text-muted-foreground">免费档不产生支付单。</p>
            ) : (
              <div className="mt-2 flex min-h-0 flex-1 flex-col gap-1.5">
                <p className="text-[11px] font-medium text-muted-foreground">选择支付方式</p>
                {(['wechat', 'alipay'] as const).map((method) => {
                  const tint = payTint[method]
                  const active = provider === method
                  return (
                    <button key={method} type="button" className={`flex h-9 items-center gap-2 rounded-lg border px-2.5 text-left text-xs font-medium ${active ? tint.active : tint.idle}`} onClick={() => setProvider(method)}>
                      <PayBrandMark method={method} className="size-5 shrink-0" />
                      <span>{method === 'wechat' ? '微信支付' : '支付宝'}</span>
                    </button>
                  )
                })}
                {summary?.payment_testing && <p className="text-[11px] leading-4 text-muted-foreground">测试实付 ¥0.10</p>}
                {qr && (
                  <div className="flex min-h-0 flex-1 flex-col items-center justify-center rounded-lg border border-border bg-secondary/40 px-2 py-1.5">
                    {qrImage ? (
                      <button type="button" className="group flex flex-col items-center gap-1" onClick={() => openWechatPay(qr)} title="打开微信付款">
                        <img src={qrImage} alt="微信支付二维码" width={112} height={112} className="size-[112px] rounded-md bg-white p-0.5 ring-offset-2 transition group-active:ring-2 group-active:ring-emerald-500" />
                        <span className="text-[10px] font-medium text-emerald-700">点二维码打开微信付款</span>
                      </button>
                    ) : (
                      <p className="text-[11px] text-muted-foreground">正在生成二维码…</p>
                    )}
                    <p className="mt-1 text-center text-[10px] leading-3 text-muted-foreground">也可另开微信扫一扫；付完后查询入账</p>
                    <button type="button" className="mt-1.5 h-8 w-full rounded-full bg-emerald-600 text-xs font-medium text-white" onClick={() => openWechatPay(qr)}>打开微信付款</button>
                  </div>
                )}
                <button disabled={busy} className="mt-auto h-8 rounded-full bg-primary text-sm text-primary-foreground disabled:opacity-50" onClick={() => {
                  const plan = planFor(summary?.plans || [], tier, cycle)
                  if (plan) void checkout(plan.id, provider)
                }}>{qr ? '重新下单' : '立即订阅'}</button>
              </div>
            )}
          </aside>
        </div>
      </section>
      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="font-semibold">订阅</h2>
        <p className="mt-2 text-sm text-muted-foreground">{active ? `${subscribedName(summary?.plans || [], active.plan_id || active.plan)} · ${statusLabel[active.status] || active.status}` : '还没有生效中的付费订阅。'}</p>
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
