'use client'

import { useEffect, useState } from 'react'
import {
  BadgeCheck,
  CircleDollarSign,
  Clock3,
  MailCheck,
  MailOpen,
  MousePointerClick,
  Send,
  ShieldAlert,
  Target,
  Timer,
  type LucideIcon,
} from 'lucide-react'
import { MetricDetail } from '@/components/metric-detail'
import { MetricCard, PageHeader, StatusBadge } from './components'
import { MetricBand, Metrics, Rate, duration, percent } from '@/lib/api'
import { adminApi } from '@/lib/admin-session'

const headline: Array<[string, string, LucideIcon, string]> = [
  ['net_margin', '利润率', CircleDollarSign, 'N/R · 四率'],
  ['act_r', '行动率', MousePointerClick, '一键获客或采纳 ÷ 完成报告 · 四率'],
  ['tr', '触达率', Send, 'D ÷ A · 四率'],
  ['open_r', '打开率', MailOpen, 'unique 打开 ÷ D · 四率'],
  ['ar', '获客率', Target, 'W ÷ D · 北星'],
]

const secondary: Array<[string, string, LucideIcon, string]> = [
  ['qr', '线索合格率', BadgeCheck, 'score≥θ ÷ 入库 · 质量'],
  ['act_r_cold', '冷客激活率', Timer, 'open 或 reply ÷ 入队 · 生命周期'],
  ['rec_r', '召回成功率', MailCheck, '回暖 ÷ 召回触达 · 生命周期'],
]

const timings: Array<[string, string, string, string, string]> = [
  ['ana_t', '分析时效', 'AnaT', '完成 − 请求', '≤2 分钟'],
  ['lead_t', '线索时效', 'LeadT', 'discovery 成功 − 发起', '≤3 分钟'],
  ['acq_t', '获客时效', 'AcqT', 'first_W − first_delivered', '≤3 天'],
  ['act_t', '激活时效', 'ActT', '首封 delivered − 入队', '≤24 小时'],
  ['rec_t', '召回时效', 'RecT', '首封 delivered − 触发', '≤24 小时'],
]

function KpiBands({ bands }: { bands: MetricBand[] }) {
  const rows: Array<[string, string, 'rate' | 'time']> = [
    ...headline.map(([key, label]) => [key, label, 'rate'] as [string, string, 'rate']),
    ...secondary.map(([key, label]) => [key, label, 'rate'] as [string, string, 'rate']),
    ...timings.map(([key, label]) => [key, label, 'time'] as [string, string, 'time']),
  ]
  return (
    <section className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-4">
        <h2 className="font-semibold text-slate-900">八率五时效 · 三档人均</h2>
        <p className="mt-1 text-xs text-slate-400">每一项单独排序后去掉两端。10–90 去掉最少，30–70 去掉最多。人数少时三档结果相同。</p>
      </div>
      <div className="grid gap-3 p-5 md:grid-cols-3">
        {bands.map((band) => (
          <article key={band.band} className="rounded-2xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{band.band}</p>
            <p className="mt-1 text-xs text-slate-500">有效用户 {band.users} 人</p>
            <ul className="mt-3 space-y-1.5 text-sm">
              {rows.map(([key, label, kind]) => {
                const rate = band.rates[key]
                const timing = band.timings[key]
                const kept = kind === 'rate' ? rate?.kept : timing?.kept
                const samples = kind === 'rate' ? rate?.samples : timing?.samples
                const value = kind === 'rate' ? percent(rate?.value) : duration(timing?.value)
                return (
                  <li key={key} className="flex items-baseline justify-between gap-3">
                    <span className="text-slate-600">{label}</span>
                    <span className="text-right font-medium text-slate-950">
                      {value}
                      <span className="ml-2 text-xs font-normal text-slate-400">{kept ?? 0}/{samples ?? 0}</span>
                    </span>
                  </li>
                )
              })}
            </ul>
          </article>
        ))}
      </div>
    </section>
  )
}

function passed(value: string | number | null | undefined, target: string | number | undefined, mode: 'gte' | 'lte' | 'lt') {
  if (value == null || value === '' || target == null || target === '') return null
  const current = Number(value)
  const goal = Number(target)
  if (Number.isNaN(current) || Number.isNaN(goal)) return null
  if (mode === 'gte') return current >= goal
  if (mode === 'lte') return current <= goal
  return current < goal
}

function statusNote(ok: boolean | null, detail: string) {
  if (ok == null) return detail
  return `${detail} · ${ok ? '达标' : '未达标'}`
}

function toneFor(ok: boolean | null) {
  if (ok == null) return 'slate' as const
  return ok ? ('green' as const) : ('red' as const)
}

export default function AdminOverviewPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState('')
  const [openKey, setOpenKey] = useState<string | null>(null)

  useEffect(() => {
    adminApi<Metrics>('/admin/metrics/cohort')
      .then(setMetrics)
      .catch((reason: Error) => setError(reason.message))
  }, [])

  const deliveryOk = passed(metrics?.redlines.delivery_rate, 0.95, 'gte')
  const bounceOk = passed(metrics?.redlines.bounce_rate, 0.015, 'lt')
  const complaintOk = passed(metrics?.redlines.complaint_rate, 0.001, 'lt')

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader
        eyebrow="30 天 · 全站中间平均"
        title="运营总览"
        description={`八率五时效按有效用户计算。已去掉演示、停用、删除、示例邮箱，以及窗口内没有报告和获客的账号。纳入 ${metrics?.basis?.included ?? 0} 人，排除 ${metrics?.basis?.excluded ?? 0} 人。卡片是去掉前后各四分之一后的中间平均。下方三档分别保留 10–90、20–80、30–70 分位之间的人。`}
      />

      {error && (
        <p className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}
      {metrics?.redlines.tripped && (
        <p className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          送达红线已触发，应限流。按封送达率 {percent(metrics.redlines.delivery_rate)}，退信 {percent(metrics.redlines.bounce_rate)}，投诉 {percent(metrics.redlines.complaint_rate)}。
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {headline.map(([key, label, icon, formula]) => {
          const rate = metrics?.rates[key] as Rate | undefined
          const ok = passed(rate?.value, rate?.target, 'gte')
          return (
            <MetricCard
              key={key}
              label={`${label} ${rate?.code ?? ''}`.trim()}
              value={percent(rate?.value)}
              icon={icon}
              tone={toneFor(ok)}
              highlight={key === 'ar'}
              note={statusNote(ok, `目标 ${percent(rate?.target)} · ${formula}`)}
              onClick={() => setOpenKey(key)}
            />
          )
        })}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        {secondary.map(([key, label, icon, formula]) => {
          const rate = metrics?.rates[key] as Rate | undefined
          const ok = passed(rate?.value, rate?.target, 'gte')
          return (
            <MetricCard
              key={key}
              label={`${label} ${rate?.code ?? ''}`.trim()}
              value={percent(rate?.value)}
              icon={icon}
              tone={toneFor(ok)}
              note={statusNote(ok, `目标 ${percent(rate?.target)} · ${formula}`)}
              onClick={() => setOpenKey(key)}
            />
          )
        })}
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <MetricCard
          label="送达率"
          value={percent(metrics?.redlines.delivery_rate)}
          icon={Send}
          tone={toneFor(deliveryOk)}
          note={statusNote(deliveryOk, '按封 · 红线 ≥95%')}
          onClick={() => setOpenKey('delivery_rate')}
        />
        <MetricCard
          label="退信率"
          value={percent(metrics?.redlines.bounce_rate)}
          icon={ShieldAlert}
          tone={toneFor(bounceOk)}
          note={statusNote(bounceOk, '按封 · 红线 <1.5%')}
          onClick={() => setOpenKey('bounce_rate')}
        />
        <MetricCard
          label="投诉率"
          value={percent(metrics?.redlines.complaint_rate)}
          icon={ShieldAlert}
          tone={toneFor(complaintOk)}
          note={statusNote(complaintOk, '按封 · 红线 <0.1%')}
          onClick={() => setOpenKey('complaint_rate')}
        />
      </div>

      <details open className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">五时效</h2>
            <p className="mt-1 text-xs text-slate-400">P50，超时记未达标</p>
          </div>
          <Clock3 className="size-5 text-blue-600" />
        </summary>
        <div className="grid gap-4 border-t border-slate-100 p-5 sm:grid-cols-2 xl:grid-cols-5">
          {timings.map(([key, label, code, formula, goal]) => {
            const value = metrics?.timings_p50_seconds[key]
            const target = metrics?.timing_targets_seconds[key]
            const ok = passed(value, target, 'lte')
            return (
              <button key={key} type="button" className="rounded-xl border border-slate-200 p-4 text-left" onClick={() => setOpenKey(key)}>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-slate-700">{label}</div>
                  <StatusBadge tone={toneFor(ok)}>{ok == null ? '—' : ok ? '达标' : '未达标'}</StatusBadge>
                </div>
                <div className="mt-3 text-2xl font-bold tracking-tight text-slate-950">{duration(value)}</div>
                <div className="mt-1 text-xs text-slate-400">
                  {code} · 目标 {goal} · {formula}
                </div>
              </button>
            )
          })}
        </div>
        {metrics?.alerts.act_or_rec_p95_over_72h && (
          <p className="border-t border-red-100 bg-red-50 px-5 py-3 text-sm text-red-700">激活时效或召回时效的 P95 超过 72 小时。</p>
        )}
      </details>

      {!!metrics?.bands?.length && <KpiBands bands={metrics.bands} />}

      <p className="mt-4 text-xs leading-5 text-slate-400">
        导入成功率 {percent(metrics?.import_success_rate)} · 账本对账成功率 — · 完成报告 {metrics?.counts.analyses ?? 0} · 一键获客 {metrics?.counts.acquired ?? 0} · 线索 {metrics?.counts.leads ?? 0} · 受众 {metrics?.counts.audience ?? 0} · 送达人数 {metrics?.counts.delivered_people ?? 0}
      </p>
      {openKey && (
        <MetricDetail
          termKey={openKey}
          value={
            openKey in (metrics?.timings_p50_seconds || {})
              ? duration(metrics?.timings_p50_seconds[openKey])
              : openKey === 'delivery_rate' || openKey === 'bounce_rate' || openKey === 'complaint_rate'
                ? percent(metrics?.redlines[openKey])
                : percent(metrics?.rates[openKey]?.value)
          }
          averaged
          basis={metrics?.basis}
          onClose={() => setOpenKey(null)}
        />
      )}
    </div>
  )
}
