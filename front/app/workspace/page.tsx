'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { MetricDetail } from '@/components/metric-detail'
import { Metrics, Rate, api, duration, percent } from '@/lib/api'

const rateOrder = [
  ['net_margin', '利润率'],
  ['act_r', '行动率'],
  ['tr', '触达率'],
  ['open_r', '打开率'],
  ['ar', '获客率'],
  ['qr', '线索合格率'],
  ['act_r_cold', '冷客激活率'],
  ['rec_r', '召回成功率'],
] as const

const timingOrder = [
  ['ana_t', '分析时效 AnaT', '≤ 2 分钟'],
  ['lead_t', '线索时效 LeadT', '≤ 3 分钟'],
  ['acq_t', '获客时效 AcqT', '≤ 3 天'],
  ['act_t', '激活时效 ActT', '≤ 24 小时'],
  ['rec_t', '召回时效 RecT', '≤ 24 小时'],
] as const

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState('')
  const [openKey, setOpenKey] = useState<string | null>(null)

  useEffect(() => {
    api<Metrics>('/metrics').then(setMetrics).catch((reason: Error) => setError(reason.message))
  }, [])

  const averaged = metrics?.display_source === 'platform_average'
  const shown = averaged && metrics?.benchmark ? metrics.benchmark : metrics
  const openValue = openKey ? cardValue(openKey, shown) : ''

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">{averaged ? '30 天 · 全站中间平均' : '30 天 · 本账号'}</span>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">八率五时效</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            {averaged
              ? `还没有获客，显示全站平均。纳入 ${shown?.basis?.included ?? 0} 人。点卡片看公式。`
              : '按本账号最近 30 天计算。点卡片看公式。'}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/workspace/products" className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">去选品分析</Link>
          <Link href="/workspace/acquire" className="rounded-lg border border-border px-3 py-2 text-sm">去获客经营</Link>
        </div>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {shown?.redlines.tripped && (
        <p className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          送达红线已触发。按封送达率 {percent(shown.redlines.delivery_rate)}，退信 {percent(shown.redlines.bounce_rate)}，投诉 {percent(shown.redlines.complaint_rate)}。目标是送达 ≥95%、退信 &lt;1.5%、投诉 &lt;0.1%。
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {rateOrder.map(([key, label]) => (
          <RateCard key={key} label={label} rate={shown?.rates[key]} emphasize={key === 'ar'} averaged={averaged} onOpen={() => setOpenKey(key)} />
        ))}
      </div>
      <div className="rounded-2xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold">五时效（P50，超时记入未达标）</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-5">
          {timingOrder.map(([key, label, target]) => (
            <button key={key} type="button" className="soft-card p-3 text-left" onClick={() => setOpenKey(key)}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="mt-2 text-lg font-semibold">{duration(shown?.timings_p50_seconds[key])}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">目标 {target}</p>
            </button>
          ))}
        </div>
        {shown?.alerts.act_or_rec_p95_over_72h && <p className="mt-3 text-sm text-destructive">激活或召回 P95 超过 72 小时。</p>}
      </div>
      <p className="text-xs text-muted-foreground">导入成功率 {percent(shown?.import_success_rate)} · 完成报告 {shown?.counts.analyses ?? 0} · 一键获客 {shown?.counts.acquired ?? 0} · 线索 {shown?.counts.leads ?? 0}</p>
      {openKey && (
        <MetricDetail
          termKey={openKey}
          value={openValue}
          averaged={averaged}
          basis={shown?.basis}
          inputs={averaged ? null : metrics?.inputs}
          onClose={() => setOpenKey(null)}
        />
      )}
    </div>
  )
}

function cardValue(key: string, source: Metrics | null) {
  if (!source) return '—'
  if (key in (source.timings_p50_seconds || {})) return duration(source.timings_p50_seconds[key])
  if (key === 'delivery_rate' || key === 'bounce_rate' || key === 'complaint_rate') return percent(source.redlines[key])
  return percent(source.rates[key]?.value)
}

function RateCard({ label, rate, emphasize = false, averaged = false, onOpen }: { label: string; rate?: Rate; emphasize?: boolean; averaged?: boolean; onOpen: () => void }) {
  return (
    <button type="button" className={`soft-card p-4 text-left transition hover:-translate-y-0.5 ${emphasize ? 'is-focus' : ''}`} onClick={onOpen}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span>{averaged ? '全站平均' : rate?.code}</span>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight">{percent(rate?.value)}</p>
      <p className="mt-2 text-[11px] text-muted-foreground">目标 {percent(rate?.target)}{emphasize ? ' · 北星' : ''}</p>
    </button>
  )
}
