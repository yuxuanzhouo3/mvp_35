'use client'

import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { adminApi, downloadText } from '@/lib/admin-session'
import { EmptyState, Notice, PageHeader, Panel, chartTooltipStyle, secondaryButton, selectClass } from '../components'

type SectionStat = {
  section: string
  label: string
  path?: string
  dwells: number
  dwell_ms: number
  avg_dwell_ms: number
  click_runs: number
  clicks: number
  click_ms: number
  avg_click_ms: number
  leaves: number
  leave_ms: number
  attention_ms: number
  visits: number
}
type DesignPick = {
  section: string
  label: string
  reason: string
  attention_ms: number
  leaves: number
  avg_dwell_ms: number
} | null
type Analytics = {
  events: Array<{ name: string; count: number }>
  funnel: Array<{ label: string; value: number }>
  behavior?: { sections: SectionStat[]; best: DesignPick; worst: DesignPick }
  window_days: number | null
}

function stay(ms: number) {
  if (!ms) return '0 秒'
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${Math.max(seconds, 1)} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分`
}

export default function AnalyticsPage() {
  const [windowDays, setWindowDays] = useState('30')
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState('')
  const [filter, setFilter] = useState('')

  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get('q') || ''
    setDraft(query)
    setFilter(query)
  }, [])

  useEffect(() => {
    adminApi<Analytics>(`/admin/analytics?window_days=${windowDays}`).then(setData).catch((reason: Error) => setError(reason.message))
  }, [windowDays])

  async function exportAnalytics() {
    try {
      const file = await adminApi<{ filename: string; body: Analytics }>(`/admin/analytics/export?window_days=${windowDays}`, { method: 'POST' })
      downloadText(file.filename, JSON.stringify(file.body, null, 2), 'application/json')
      setNotice('分析已导出，并写入审计日志')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '导出失败')
    }
  }

  const events = data?.events ?? []
  const funnel = data?.funnel ?? []
  const first = funnel[0]?.value || 0
  const needle = filter.trim().toLowerCase()
  const sections = (data?.behavior?.sections ?? []).filter((row) => !needle || `${row.label} ${row.section} ${row.path || ''}`.toLowerCase().includes(needle))

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Behavior analytics" title="行为分析" description="主页面和子页面都会记停留、连续点击和关闭。用搜索找出某一页的时间，停留久、连续点击多的是更好的设计，很快关掉的是更差的设计。" action={<div className="flex gap-2"><select className={selectClass} aria-label="时间范围" value={windowDays} onChange={(event) => setWindowDays(event.target.value)}><option value="7">最近 7 天</option><option value="30">最近 30 天</option><option value="90">本季度</option></select><button className={secondaryButton} onClick={() => void exportAnalytics()}>导出分析</button></div>} />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <div className="page-grid">
        <Panel title="核心事件" description={`近 ${windowDays} 天`}>
          {events.length === 0 ? <EmptyState query="事件" /> : (
            <div className="h-80 p-4"><ResponsiveContainer width="100%" height="100%"><BarChart data={events} layout="vertical" margin={{ left: 20, right: 18 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" /><XAxis type="number" axisLine={false} tickLine={false} fontSize={12} /><YAxis type="category" dataKey="name" width={140} axisLine={false} tickLine={false} fontSize={11} /><Tooltip contentStyle={chartTooltipStyle} /><Bar dataKey="count" name="次数" fill="#2563eb" radius={[0, 7, 7, 0]} /></BarChart></ResponsiveContainer></div>
          )}
        </Panel>
        <Panel title="默认激活漏斗" description="当前窗口内的存量">
          {funnel.length === 0 ? <EmptyState query="漏斗" /> : (
            <div className="space-y-3 p-5">{funnel.map((step) => {
              const rate = first ? Math.round((step.value / first) * 1000) / 10 : 0
              return <div key={step.label}><div className="mb-1 flex justify-between text-sm"><span className="font-medium">{step.label}</span><span>{step.value.toLocaleString()} · {rate}%</span></div><div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-blue-600" style={{ width: `${Math.max(rate, step.value ? 6 : 0)}%` }} /></div></div>
            })}</div>
          )}
        </Panel>
      </div>
      <Panel title="页面停留" description="每一条主页面和子页面都在表里。没有访客时时间为 0。搜索后只留下匹配的页面。" className="mt-5" action={
        <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); setFilter(draft.trim()) }}>
          <input value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="搜索页面" placeholder="搜索页面或区块" className="admin-focus w-40 rounded-xl border border-slate-200 px-3 py-2 text-sm sm:w-56" />
          <button className={secondaryButton} type="submit">搜索</button>
        </form>
      }>
        {sections.length === 0 ? <EmptyState query={filter || '页面停留'} /> : (
          <div className="space-y-4 p-5">
            <div className="grid gap-3 md:grid-cols-2">
              <article className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-xs font-semibold text-emerald-700">更好的设计</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">{data?.behavior?.best?.label ?? '—'}</p>
                <p className="mt-1 text-xs text-slate-600">{data?.behavior?.best?.reason} · 关注 {stay(data?.behavior?.best?.attention_ms ?? 0)}</p>
              </article>
              <article className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs font-semibold text-amber-800">更差的设计</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">{data?.behavior?.worst?.label ?? '—'}</p>
                <p className="mt-1 text-xs text-slate-600">{data?.behavior?.worst?.reason} · 关闭 {data?.behavior?.worst?.leaves ?? 0} 次 · 平均停留 {stay(data?.behavior?.worst?.avg_dwell_ms ?? 0)}</p>
              </article>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="text-xs text-slate-500">
                  <tr>
                    <th className="py-2 pr-3 font-medium">页面</th>
                    <th className="py-2 pr-3 font-medium">路径</th>
                    <th className="py-2 pr-3 font-medium">停留次数</th>
                    <th className="py-2 pr-3 font-medium">平均停留</th>
                    <th className="py-2 pr-3 font-medium">连续点击</th>
                    <th className="py-2 pr-3 font-medium">点击时长</th>
                    <th className="py-2 pr-3 font-medium">关闭次数</th>
                    <th className="py-2 font-medium">关闭前停留</th>
                  </tr>
                </thead>
                <tbody>
                  {sections.map((row) => (
                    <tr key={row.section} className="border-t border-slate-100">
                      <td className="py-2 pr-3 font-medium text-slate-900">{row.label}</td>
                      <td className="py-2 pr-3 font-mono text-xs text-slate-500">{row.path || '—'}</td>
                      <td className="py-2 pr-3">{row.dwells}</td>
                      <td className="py-2 pr-3">{stay(row.avg_dwell_ms)}</td>
                      <td className="py-2 pr-3">{row.click_runs} 次 · {row.clicks} 下</td>
                      <td className="py-2 pr-3">{stay(row.click_ms)}</td>
                      <td className="py-2 pr-3">{row.leaves}</td>
                      <td className="py-2">{stay(row.leave_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Panel>
    </div>
  )
}
