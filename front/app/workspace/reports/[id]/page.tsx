'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { api, percent } from '@/lib/api'

type Report = {
  id: string
  stale: boolean
  explanation: string
  explanation_model: string
  rules_version: string
  seed_analysis_id: string | null
  metrics: Record<string, string | number>
}

const tabs = [
  ['market', '市场机会'],
  ['profit', '利润测算'],
  ['tax', '税务'],
  ['logistics', '物流时效'],
  ['risk', '风险提示'],
] as const

export default function ReportPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const [report, setReport] = useState<Report | null>(null)
  const [tab, setTab] = useState<(typeof tabs)[number][0]>('market')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<Report>(`/analyses/${params.id}`).then(setReport).catch((reason: Error) => setError(reason.message))
  }, [params.id])

  const metrics = report?.metrics

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">路径 A · 报告</span>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">选品报告</h1>
          <p className="mt-2 text-sm text-muted-foreground">规则版本 {report?.rules_version || '—'} · 解释模型 {report?.explanation_model || '—'}</p>
        </div>
        <button
          disabled={!report || report.stale || busy}
          className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
          onClick={() => {
            if (!report) return
            setBusy(true)
            api<{ href: string }>(`/analyses/${report.id}/acquire`, { method: 'POST' })
              .then((data) => router.push(data.href))
              .catch((reason: Error) => setError(reason.message))
              .finally(() => setBusy(false))
          }}
        >一键获客</button>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {report?.stale && <p className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">市场或成本已经变更。这份历史报告只读，需要重新分析后才能获客。</p>}
      <div className="grid gap-3 sm:grid-cols-4">
        <Metric label="利润率 N%" value={percent(String(metrics?.net_margin ?? ''))} />
        <Metric label="净利润" value={metrics ? `$${metrics.net_profit_usd}` : '—'} />
        <Metric label="机会分" value={metrics ? String(metrics.opportunity_score) : '—'} />
        <Metric label="风险" value={metrics ? String(metrics.risk_level) : '—'} />
      </div>
      <div className="report-card">
        <div className="flex flex-wrap gap-1 border-b border-border px-3 pt-3">
          {tabs.map(([key, label]) => (
            <button key={key} className={`report-tab ${tab === key ? 'report-tab-active' : ''}`} onClick={() => setTab(key)}>{label}</button>
          ))}
        </div>
        <div className="p-5 text-sm leading-7">
          {tab === 'market' && <p>路线 {metrics?.route} · 货源 {metrics?.origin_country} · 市场 {metrics?.target_market} · 术语 {metrics?.incoterm}。机会分 {metrics?.opportunity_score}，由利润率规则折算，不是模型打分。</p>}
          {tab === 'profit' && <p>R ${metrics?.target_price_usd} − C ${metrics?.landed_cost_usd}（采购 {metrics?.purchase_usd} + 包装 {metrics?.packaging_usd} + 国内 {metrics?.domestic_usd} + 国际 {metrics?.international_usd}）− F ${metrics?.channel_fee_usd} − T ${metrics?.tax_usd} = N ${metrics?.net_profit_usd}。汇率 {metrics?.fx_usd_cny}。</p>}
          {tab === 'tax' && <p>税务口径 {metrics?.tax_regime}。关税率 {metrics?.duty_rate}，增值税率 {metrics?.vat_rate}，税费合计 ${metrics?.tax_usd}。</p>}
          {tab === 'logistics' && <p>预计时效 {metrics?.transit_days_min}–{metrics?.transit_days_max} 天。国际段 ${metrics?.international_usd}。</p>}
          {tab === 'risk' && <p>风险等级 {metrics?.risk_level}。推荐线是利润率 15%。低于该线时先复核成本或售价。</p>}
        </div>
      </div>
      <p className="rounded-2xl border border-border bg-muted/40 p-4 text-sm leading-7">{report?.explanation}</p>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <article className="rounded-2xl border border-border bg-card p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold">{value || '—'}</p></article>
}
