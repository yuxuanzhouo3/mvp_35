'use client'

import { Activity, BarChart3, Clock3, MousePointer2, Users } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { MetricCard, PageHeader, Panel, StatusBadge, chartTooltipStyle, secondaryButton, selectClass } from '../components'

const events = [
  { name: 'page_viewed', users: 12480, events: 48216, change: 12.2 },
  { name: 'signup_completed', users: 3420, events: 3420, change: 8.6 },
  { name: 'product_analysis_completed', users: 2156, events: 8942, change: 15.8 },
  { name: 'lead_discovery_completed', users: 1384, events: 4681, change: 9.1 },
  { name: 'outreach_sent', users: 742, events: 12036, change: -2.4 },
]

const retention = [
  { cohort: '08/05', d1: 72, d7: 54, d30: 31 }, { cohort: '08/12', d1: 75, d7: 57, d30: 34 },
  { cohort: '08/19', d1: 78, d7: 61, d30: 36 }, { cohort: '08/26', d1: 80, d7: 64, d30: 0 },
  { cohort: '09/02', d1: 82, d7: 67, d30: 0 },
]

export default function AnalyticsPage() {
  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Behavior analytics" title="行为分析" description="参考 mvp_1 的设备统计和 mvp_26 的分层分析接口，提供事件、漏斗、留存与功能采用率。" action={<div className="flex gap-2"><select className={selectClass} aria-label="时间范围"><option>最近 30 天</option><option>最近 7 天</option><option>本季度</option></select><button className={secondaryButton}>导出分析</button></div>} />
      <div className="metric-grid mb-5">
        <MetricCard label="核心事件数" value="286K" change="+11.4%" icon={MousePointer2} />
        <MetricCard label="事件用户数" value="12,480" change="+8.2%" icon={Users} tone="green" />
        <MetricCard label="事件完整率" value="99.7%" change="+0.2%" icon={Activity} tone="violet" />
        <MetricCard label="数据延迟" value="4m 12s" change="-18s" icon={Clock3} tone="amber" />
      </div>
      <div className="page-grid">
        <Panel title="核心事件趋势" description="用户数 · 近 30 天">
          <div className="h-80 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={events} layout="vertical" margin={{ left: 35, right: 18 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" axisLine={false} tickLine={false} fontSize={12} />
                <YAxis type="category" dataKey="name" width={160} axisLine={false} tickLine={false} fontSize={11} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="users" name="用户数" radius={[0, 7, 7, 0]}>{events.map((_, index) => <Cell key={index} fill={index < 2 ? '#2563eb' : '#60a5fa'} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="默认激活漏斗" description="注册后 7 日转化窗口">
          <div className="p-5">
            {[
              ['完成注册', 3420, 100], ['创建企业', 3118, 91.2], ['导入商品', 2512, 73.5],
              ['完成分析', 2156, 63.0], ['发现客户', 1384, 40.5],
            ].map(([label, value, rate], index) => (
              <div key={label} className="relative mb-2 overflow-hidden rounded-xl bg-slate-100 p-3" style={{ width: `${100 - index * 7}%`, marginInline: 'auto' }}>
                <div className="relative z-10 flex justify-between text-sm"><span className="font-medium">{label}</span><span>{Number(value).toLocaleString()} · {rate}%</span></div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="用户留存 Cohort" description="以完成注册为起点，以核心业务事件为回访" className="mt-5" action={<BarChart3 className="size-5 text-blue-600" />}>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead><tr><th>注册周</th><th>新用户</th><th>次日留存</th><th>7 日留存</th><th>30 日留存</th><th>状态</th></tr></thead>
            <tbody>{retention.map((row, index) => <tr key={row.cohort}><td className="font-medium">{row.cohort}</td><td>{820 + index * 74}</td><td className="font-semibold text-blue-700">{row.d1}%</td><td className="font-semibold text-cyan-700">{row.d7}%</td><td>{row.d30 ? `${row.d30}%` : '—'}</td><td><StatusBadge tone={index > 2 ? 'green' : 'blue'}>{index > 2 ? '提升' : '稳定'}</StatusBadge></td></tr>)}</tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}
