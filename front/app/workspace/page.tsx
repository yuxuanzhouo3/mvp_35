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
    <div className="flex flex-col gap-2 pb-[calc(6.5rem+env(safe-area-inset-bottom))] text-[12px] leading-4 md:gap-4 md:pb-0 md:text-sm md:leading-5">
      <div className="flex flex-wrap items-end justify-between gap-2 md:gap-4">
        <div className="min-w-0">
          <span className="eyebrow">{averaged ? '30 天 · 全站中间平均' : '30 天 · 本账号'}</span>
          <h1 className="mt-1 text-base font-semibold tracking-tight md:mt-2 md:text-3xl">八率五时效</h1>
          <p className="mt-1 max-w-2xl text-[11px] leading-4 text-muted-foreground md:mt-2 md:text-sm md:leading-6">
            {averaged
              ? `还没有获客，显示全站平均。纳入 ${shown?.basis?.included ?? 0} 人。点卡片看公式。`
              : '按本账号最近 30 天计算。点卡片看公式。'}
          </p>
        </div>
        <div className="flex gap-1.5 md:gap-2">
          <Link href="/workspace/products" className="rounded-lg bg-primary px-2.5 py-1.5 text-[11px] text-primary-foreground md:px-3 md:py-2 md:text-sm">去选品</Link>
          <Link href="/workspace/acquire" className="rounded-lg border border-border px-2.5 py-1.5 text-[11px] md:px-3 md:py-2 md:text-sm">去获客</Link>
        </div>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive md:px-4 md:py-3 md:text-sm">{error}</p>}
      {shown?.redlines.tripped && (
        <p className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-[11px] leading-4 text-amber-900 md:px-4 md:py-3 md:text-sm md:leading-5">
          送达红线已触发。按封送达率 {percent(shown.redlines.delivery_rate)}，退信 {percent(shown.redlines.bounce_rate)}，投诉 {percent(shown.redlines.complaint_rate)}。
        </p>
      )}
      <div className="grid grid-cols-4 gap-1.5 md:grid-cols-2 md:gap-3 xl:grid-cols-4">
        {rateOrder.map(([key, label]) => (
          <RateCard key={key} label={label} rate={shown?.rates[key]} emphasize={key === 'ar'} averaged={averaged} onOpen={() => setOpenKey(key)} />
        ))}
      </div>
      <div className="rounded-2xl border border-border bg-card p-2.5 md:p-5">
        <h2 className="text-[11px] font-semibold md:text-sm">五时效（P50）</h2>
        <div className="mt-2 grid grid-cols-5 gap-1 md:mt-4 md:gap-3">
          {timingOrder.map(([key, label, target]) => (
            <button key={key} type="button" className="rounded-xl border border-border bg-background/80 px-1 py-1.5 text-left md:rounded-[1.15rem] md:p-3" onClick={() => setOpenKey(key)}>
              <p className="truncate text-[9px] leading-3 text-muted-foreground md:text-xs md:leading-4">{label.replace(/（|）|\(.+\)/g, '').replace(/ AnaT| LeadT| AcqT| ActT| RecT/g, '')}</p>
              <p className="mt-0.5 text-[11px] font-semibold md:mt-2 md:text-lg">{duration(shown?.timings_p50_seconds[key])}</p>
              <p className="mt-0.5 hidden text-[11px] text-muted-foreground md:block">目标 {target}</p>
            </button>
          ))}
        </div>
        {shown?.alerts.act_or_rec_p95_over_72h && <p className="mt-2 text-xs text-destructive md:mt-3 md:text-sm">激活或召回 P95 超过 72 小时。</p>}
      </div>
      <p className="text-[10px] text-muted-foreground md:text-xs">导入 {percent(shown?.import_success_rate)} · 报告 {shown?.counts.analyses ?? 0} · 获客 {shown?.counts.acquired ?? 0} · 线索 {shown?.counts.leads ?? 0}</p>
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
    <button type="button" className={`rounded-xl border border-border p-1.5 text-left transition hover:-translate-y-0.5 md:rounded-[1.15rem] md:p-4 ${emphasize ? 'border-primary/40 bg-primary/5 ring-1 ring-primary/20' : 'bg-card'}`} onClick={onOpen}>
      <div className="flex items-center justify-between gap-0.5 text-[9px] leading-3 text-muted-foreground md:text-xs md:leading-4">
        <span className="truncate">{label}</span>
        <span className="hidden shrink-0 sm:inline">{averaged ? '平均' : rate?.code}</span>
      </div>
      <p className="mt-1 text-sm font-semibold tracking-tight md:mt-3 md:text-3xl">{percent(rate?.value)}</p>
      <p className="mt-0.5 truncate text-[9px] text-muted-foreground md:mt-2 md:text-[11px]">目标 {percent(rate?.target)}{emphasize ? ' · 北星' : ''}</p>
    </button>
  )
}
