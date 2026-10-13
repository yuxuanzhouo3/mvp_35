'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { api, percent } from '@/lib/api'
import { AdSlot } from '@/components/ad-slot'
import { ReportDialog } from '@/components/report-dialog'
import { TermHint, type SelectionTermId } from '@/components/term-hint'

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
    <div>
      <p className="text-sm text-muted-foreground">报告在页面中央打开，读完可以关闭。</p>
      <ReportDialog title="选品报告" onClose={() => router.push('/workspace/products')}>
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="text-xs text-muted-foreground inline-flex items-center">规则版本 {report?.rules_version || '—'}<TermHint id="rules" /> · 解释模型 {report?.explanation_model || '—'}</div>
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
            <TermHint id="acquire" />
          </div>
          {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
          {report?.stale && <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">市场或成本已经变更。这份历史报告只读<TermHint id="stale" />，需要重新分析后才能获客。</div>}
          <div className="grid grid-cols-2 gap-3">
            <Metric label="利润率 N%" hint="margin" value={percent(String(metrics?.net_margin ?? ''))} />
            <Metric label="净利润" hint="profit" value={metrics ? `$${metrics.net_profit_usd}` : '—'} />
            <Metric label="机会分" hint="score" value={metrics ? String(metrics.opportunity_score) : '—'} />
            <Metric label="风险" hint="risk" value={metrics ? String(metrics.risk_level) : '—'} />
          </div>
          <div className="flex gap-1 overflow-x-auto border-b border-border">
            {tabs.map(([key, label]) => (
              <button key={key} className={`report-tab shrink-0 ${tab === key ? 'report-tab-active' : ''}`} onClick={() => setTab(key)}>{label}</button>
            ))}
          </div>
          <div className="text-sm leading-7">
            {tab === 'market' && <div>路线<TermHint id="route" /> {metrics?.route} · 货源<TermHint id="origin" /> {metrics?.origin_country} · 市场<TermHint id="market" /> {metrics?.target_market} · 术语<TermHint id="incoterm" /> {metrics?.incoterm}。机会分<TermHint id="score" /> {metrics?.opportunity_score}，由利润率规则折算，不是模型打分。</div>}
            {tab === 'profit' && <div>售价<TermHint id="price" /> ${metrics?.target_price_usd} − 到岸成本 ${metrics?.landed_cost_usd}（采购<TermHint id="cost" /> {metrics?.purchase_usd} + 包装<TermHint id="packaging" /> {metrics?.packaging_usd} + 国内段<TermHint id="domestic" /> {metrics?.domestic_usd} + 国际段<TermHint id="international" /> {metrics?.international_usd}）− 渠道费<TermHint id="fee" /> ${metrics?.channel_fee_usd} − 税费 ${metrics?.tax_usd} = 净利润<TermHint id="profit" /> ${metrics?.net_profit_usd}。汇率<TermHint id="fx" /> {metrics?.fx_usd_cny}。</div>}
            {tab === 'tax' && <div>税务口径<TermHint id="tax" /> {metrics?.tax_regime}。关税<TermHint id="duty" /> {metrics?.duty_rate}，增值税<TermHint id="vat" /> {metrics?.vat_rate}，税费合计 ${metrics?.tax_usd}。</div>}
            {tab === 'logistics' && <div>预计时效<TermHint id="transit" /> {metrics?.transit_days_min}–{metrics?.transit_days_max} 天。国际段<TermHint id="international" /> ${metrics?.international_usd}。</div>}
            {tab === 'risk' && <div>风险<TermHint id="risk" /> {metrics?.risk_level}。推荐线是利润率<TermHint id="margin" /> 15%<TermHint id="floor" />。低于该线时先复核成本或售价。</div>}
          </div>
          <p className="rounded-xl border border-border bg-muted/40 p-3 text-sm leading-6">{report?.explanation}</p>
          <AdSlot placement="report_footer" />
        </div>
      </ReportDialog>
    </div>
  )
}

function Metric({ label, hint, value }: { label: string; hint?: SelectionTermId; value: string }) {
  return <article className="rounded-2xl border border-border bg-card p-4"><div className="text-xs text-muted-foreground inline-flex items-center">{label}{hint && <TermHint id={hint} />}</div><p className="mt-2 text-2xl font-semibold">{value || '—'}</p></article>
}
