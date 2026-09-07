'use client'

import { Activity, AlertTriangle, ArrowUpRight, CircleDollarSign, MailCheck, Megaphone, UserPlus, Users } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { MetricCard, PageHeader, Panel, StatusBadge, chartTooltipStyle, secondaryButton } from './components'

const trend = [
  { date: '08/09', newUsers: 92, activeUsers: 412 }, { date: '08/14', newUsers: 118, activeUsers: 468 },
  { date: '08/19', newUsers: 104, activeUsers: 501 }, { date: '08/24', newUsers: 146, activeUsers: 558 },
  { date: '08/29', newUsers: 163, activeUsers: 604 }, { date: '09/03', newUsers: 181, activeUsers: 671 },
  { date: '09/07', newUsers: 198, activeUsers: 724 },
]

const funnel = [
  ['访问官网', 12480, 100], ['完成注册', 3420, 27.4], ['首次分析', 2156, 17.3],
  ['发现客户', 1384, 11.1], ['首次触达', 742, 5.9], ['购买套餐', 286, 2.3],
] as const

export default function OverviewPage() {
  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Operations overview" title="运营总览" description="从广告获客、用户激活到邀请与召回，统一查看平台增长和风险。" action={<button className={secondaryButton}>最近 30 天</button>} />
      <div className="metric-grid">
        <MetricCard label="总用户" value="38,426" change="+12.8%" icon={Users} />
        <MetricCard label="月活用户" value="9,842" change="+9.4%" icon={Activity} tone="green" />
        <MetricCard label="7 日激活率" value="63.1%" change="+3.2%" icon={UserPlus} tone="violet" />
        <MetricCard label="付费转化" value="8.36%" change="+0.7%" icon={CircleDollarSign} tone="amber" />
      </div>

      <div className="page-grid mt-5">
        <Panel title="新增与活跃趋势" description="小时汇总 · 最后更新 12:00">
          <div className="h-80 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ left: -16, right: 8, top: 8 }}>
                <defs><linearGradient id="active" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#2563eb" stopOpacity={0.25} /><stop offset="95%" stopColor="#2563eb" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis tickLine={false} axisLine={false} fontSize={12} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Area type="monotone" dataKey="activeUsers" name="活跃用户" stroke="#2563eb" strokeWidth={2} fill="url(#active)" />
                <Area type="monotone" dataKey="newUsers" name="新增用户" stroke="#10b981" strokeWidth={2} fill="transparent" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="核心转化漏斗" description="访问官网 → 购买套餐">
          <div className="space-y-3 p-5">
            {funnel.map(([label, value, rate]) => (
              <div key={label}>
                <div className="mb-1.5 flex justify-between text-sm"><span className="font-medium text-slate-700">{label}</span><span className="text-slate-500">{value.toLocaleString()} · {rate}%</span></div>
                <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-gradient-to-r from-blue-600 to-cyan-400" style={{ width: `${Math.max(rate, 5)}%` }} /></div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        {[
          ['广告贡献注册', '684', '+18.2%', Megaphone, 'text-blue-600'],
          ['有效邀请', '326', '+11.6%', UserPlus, 'text-violet-600'],
          ['召回激活', '418', '+7.4%', MailCheck, 'text-emerald-600'],
        ].map(([title, value, change, Icon, color]) => (
          <div key={title as string} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between"><Icon className={`size-5 ${color}`} /><span className="text-xs font-semibold text-emerald-600">{change as string}</span></div>
            <div className="mt-4 text-2xl font-bold text-slate-950">{value as string}</div><div className="mt-1 text-sm text-slate-500">{title as string}</div>
          </div>
        ))}
      </div>

      <Panel title="待处理与风险" description="优先显示可能影响发送、转化和数据安全的事项" className="mt-5" action={<AlertTriangle className="size-5 text-amber-500" />}>
        <div className="divide-y divide-slate-100">
          {[
            ['召回活动「30 日沉默用户」投诉率接近阈值', '12 分钟前', 'red'],
            ['广告 dashboard_top 有 2 个排期冲突', '35 分钟前', 'amber'],
            ['邀请奖励复核队列有 18 条待处理', '1 小时前', 'violet'],
          ].map(([title, time, tone]) => (
            <button key={title} className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-slate-50">
              <StatusBadge tone={tone as 'red' | 'amber' | 'violet'}>需处理</StatusBadge>
              <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-slate-800">{title}</div><div className="mt-0.5 text-xs text-slate-400">{time}</div></div>
              <ArrowUpRight className="size-4 text-slate-400" />
            </button>
          ))}
        </div>
      </Panel>
    </div>
  )
}
