'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
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

const sampleRates: Record<string, string> = {
  net_margin: '0.499',
  act_r: '0.62',
  tr: '0.96',
  open_r: '0.42',
  ar: '0.092',
  qr: '0.64',
  act_r_cold: '0.28',
  rec_r: '0.12',
}

const sampleTargets: Record<string, string> = {
  net_margin: '0.15',
  act_r: '0.5',
  tr: '0.95',
  open_r: '0.4',
  ar: '0.08',
  qr: '0.6',
  act_r_cold: '0.25',
  rec_r: '0.1',
}

const sampleTimings: Record<string, number> = {
  ana_t: 48,
  lead_t: 96,
  acq_t: 103680,
  act_t: 21600,
  rec_t: 28800,
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api<Metrics>('/metrics').then(setMetrics).catch((reason: Error) => setError(reason.message))
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">30 天 · 租户口径</span>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">八率五时效</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">首屏是四率加北星获客率。还没有本租户成交时，卡片显示样例，方便对照目标。金额仍以规则引擎为准。</p>
        </div>
        <div className="flex gap-2">
          <Link href="/workspace/products" className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">去选品分析</Link>
          <Link href="/workspace/acquire" className="rounded-lg border border-border px-3 py-2 text-sm">去获客经营</Link>
        </div>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {metrics?.redlines.tripped && (
        <p className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          送达红线已触发。按封送达率 {percent(metrics.redlines.delivery_rate)}，退信 {percent(metrics.redlines.bounce_rate)}，投诉 {percent(metrics.redlines.complaint_rate)}。目标是送达 ≥95%、退信 &lt;1.5%、投诉 &lt;0.1%。
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {rateOrder.slice(0, 5).map(([key, label]) => (
          <RateCard key={key} label={label} rate={metrics?.rates[key]} sample={sampleRates[key]} targetSample={sampleTargets[key]} emphasize={key === 'ar'} />
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {rateOrder.slice(5).map(([key, label]) => (
          <RateCard key={key} label={label} rate={metrics?.rates[key]} sample={sampleRates[key]} targetSample={sampleTargets[key]} />
        ))}
      </div>
      <details className="rounded-2xl border border-border bg-card p-5">
        <summary className="cursor-pointer text-sm font-semibold">五时效（P50，超时记入未达标）</summary>
        <div className="mt-4 grid gap-3 md:grid-cols-5">
          {timingOrder.map(([key, label, target]) => (
            <div key={key} className="rounded-xl border border-border p-3">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="mt-2 text-lg font-semibold">{duration(metrics?.timings_p50_seconds[key] ?? sampleTimings[key])}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">目标 {target}</p>
            </div>
          ))}
        </div>
        {metrics?.alerts.act_or_rec_p95_over_72h && <p className="mt-3 text-sm text-destructive">激活或召回 P95 超过 72 小时。</p>}
      </details>
      <p className="text-xs text-muted-foreground">导入成功率 {percent(metrics?.import_success_rate)} · 完成报告 {metrics?.counts.analyses ?? 0} · 一键获客 {metrics?.counts.acquired ?? 0} · 线索 {metrics?.counts.leads ?? 0}</p>
    </div>
  )
}

function RateCard({ label, rate, sample, targetSample, emphasize = false }: { label: string; rate?: Rate; sample?: string; targetSample?: string; emphasize?: boolean }) {
  const shown = rate?.value ?? sample
  const sampled = rate?.value == null && sample != null
  return (
    <article className={`rounded-2xl border p-4 ${emphasize ? 'border-primary bg-primary/5' : 'border-border bg-card'}`}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span>{sampled ? '样例' : rate?.code}</span>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight">{percent(shown)}</p>
      <p className="mt-2 text-[11px] text-muted-foreground">目标 {percent(rate?.target ?? targetSample)}{emphasize ? ' · 北星' : ''}</p>
    </article>
  )
}
