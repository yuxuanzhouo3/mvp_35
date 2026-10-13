'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { sharePlan, sharePlans, type SharePlan } from './share-plans'

type Lead = { id: string; company: string; status: string; won_at?: string | null }
type Recall = { id: string; lead_id: string; status: string; delivered_at?: string | null }
type Payment = { id: string; amount: number; status: string; plan_id?: string | null; kind?: string }
type Subscription = { status: string; plan_id?: string; plan?: string }

const deliveredLeadStatus = new Set(['contacted', 'replied', 'won', 'lost', 'silent'])

function yuan(fen: number) {
  return `¥${(fen / 100).toFixed(2)}`
}

function percent(rate: number) {
  return `${Math.round(rate * 100)}%`
}

export function RaasShare({ leads, recalls }: { leads: Lead[]; recalls: Recall[] }) {
  const [payments, setPayments] = useState<Payment[]>([])
  const [activeId, setActiveId] = useState('free')
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api<{ items: Payment[] }>('/payments'),
      api<{ items: Subscription[] }>('/subscriptions'),
    ])
      .then(([paymentData, subscriptionData]) => {
        if (cancelled) return
        setPayments(paymentData.items)
        const active = subscriptionData.items.find((item) => item.status === 'active')
        const id = active?.plan_id || active?.plan || 'free'
        setActiveId(sharePlan(id) ? id : 'free')
      })
      .catch((reason: Error) => {
        if (!cancelled) setLoadError(reason.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const plan = sharePlan(activeId) || sharePlans[0]
  const deliveredLeads = leads.filter((lead) => deliveredLeadStatus.has(lead.status))
  const claimedWins = leads.filter((lead) => lead.status === 'won' || Boolean(lead.won_at))
  const recallDelivered = recalls.filter((job) => job.status === 'sent' && job.delivered_at)
  const paid = payments.filter((payment) => payment.status === 'succeeded')
  const paidFen = paid.reduce((sum, payment) => sum + payment.amount, 0)
  const leadFen = deliveredLeads.length * plan.leadFen
  const recallFen = recallDelivered.length * plan.recallFen
  const dealFen = Math.round(paidFen * plan.take)

  const cards = [
    {
      title: '线索数量',
      count: String(deliveredLeads.length),
      rule: '已送达的线索，一人一次。刚入库、还没发出去的不算。',
      money: `${yuan(plan.leadFen)} × ${deliveredLeads.length} = ${yuan(leadFen)}`,
    },
    {
      title: '成交',
      count: String(paid.length),
      rule: '只计支付成功的回款。手点赢单和私下转账是 0。',
      money: `${percent(plan.take)} × ${yuan(paidFen)} = ${yuan(dealFen)}`,
    },
    {
      title: '召回',
      count: String(recallDelivered.length),
      rule: '召回消息已送达才计数。排队、未批准、退信都不算。',
      money: `${yuan(plan.recallFen)} × ${recallDelivered.length} = ${yuan(recallFen)}`,
    },
    {
      title: '召回成交',
      count: '0',
      rule: '召回送达之后的支付成功，且不与上面的成交重复。支付单还没挂上线索时，会员回款先算在成交里。',
      money: `${percent(plan.take)} × ¥0.00 = ¥0.00`,
    },
  ]

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="font-semibold">结果分佣</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
          线索和召回写在本系统里，送达即可统计。成交如果绕开平台，私下收款就没有凭证，所以不认手点赢单。能统计的办法是：买家付给平台收款单，支付成功才按这笔回款分佣。官网开通和账户销售必须付款才生效，因此 B9 的成交就是支付成功。
        </p>
      </div>
      {loadError && <p className="text-sm text-destructive">{loadError}</p>}
      <p className="text-sm text-muted-foreground">当前按「{plan.name}」计。计件归平台。成交抽成在支付入账之后才发生，待支付不算。</p>
      <div className="grid gap-3 md:grid-cols-2">
        {cards.map((card) => (
          <article key={card.title} className="rounded-2xl border border-border p-4">
            <h3 className="text-sm font-medium text-muted-foreground">{card.title}</h3>
            <p className="mt-1 text-3xl font-semibold tracking-tight">{card.count}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{card.rule}</p>
            <p className="mt-2 text-sm font-medium">{card.money}</p>
          </article>
        ))}
      </div>
      <p className="text-sm leading-6 text-muted-foreground">
        自行标记赢单 {claimedWins.length} 条{claimedWins.length > 0 ? `（${claimedWins.map((lead) => lead.company).join('、')}）` : ''}，没有对应的支付成功，抽成是 0。
      </p>
      <div>
        <h3 className="font-semibold">换档后跳到支付</h3>
        <p className="mt-1 text-sm text-muted-foreground">免费档不跳转。付费档进入账单页，用微信或支付宝付月费。月费付清之前，抽成仍按现在这一档。</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {sharePlans.map((item) => (
            <PlanCard key={item.id} item={item} current={item.id === plan.id} />
          ))}
        </div>
      </div>
    </div>
  )
}

function PlanCard({ item, current }: { item: SharePlan; current: boolean }) {
  return (
    <article className={`rounded-2xl border p-4 ${current ? 'border-primary bg-primary/5' : 'border-border'}`}>
      <h3 className="font-semibold">{item.name}{current ? ' · 当前' : ''}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{item.monthYuan === 0 ? '不付月费' : `¥${item.monthYuan} / 月`}</p>
      <p className="mt-2 text-sm leading-6">成交与召回成交抽成 {percent(item.take)}</p>
      <p className="text-sm leading-6 text-muted-foreground">线索 {yuan(item.leadFen)} / 条 · 召回 {yuan(item.recallFen)} / 次</p>
      {item.monthYuan > 0 ? (
        <Link href={`/workspace/billing?plan=${item.id}`} className="mt-3 inline-flex h-10 items-center rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground">去支付</Link>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">停在本页</p>
      )}
    </article>
  )
}
