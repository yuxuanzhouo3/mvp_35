'use client'

import { AlertOctagon, MailCheck, Pause, Plus, RotateCcw, UserRoundCheck, UsersRound } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { MetricCard, PageHeader, Panel, StatusBadge, chartTooltipStyle, primaryButton, secondaryButton } from '../components'

const lifecycle = [
  { name: '活跃', value: 9842, color: '#10b981' }, { name: '沉默', value: 4286, color: '#f59e0b' },
  { name: '流失风险', value: 2146, color: '#f97316' }, { name: '已流失', value: 6380, color: '#ef4444' },
]

const campaigns = [
  { name: '30 日沉默用户', audience: 4260, delivered: '96.4%', returned: '12.8%', lift: '+4.6%', status: '发送中' },
  { name: '首份分析未完成', audience: 1880, delivered: '98.1%', returned: '18.2%', lift: '+7.9%', status: '已完成' },
  { name: '专业版到期召回', audience: 642, delivered: '97.8%', returned: '21.4%', lift: '+9.2%', status: '已排期' },
  { name: '额度耗尽未升级', audience: 926, delivered: '—', returned: '—', lift: '—', status: '草稿' },
]

function campaignTone(status: string) {
  if (status === '发送中') return 'green' as const
  if (status === '已完成') return 'blue' as const
  if (status === '已排期') return 'violet' as const
  return 'slate' as const
}

export default function RecallPage() {
  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="User win-back" title="用户召回" description="平台注册用户召回独立于租户的海外线索召回；以规则分群、人工审批、频控和增量对照组保障安全。" action={<button className={primaryButton}><Plus className="size-4" /> 新建召回活动</button>} />
      <div className="metric-grid mb-5">
        <MetricCard label="待召回用户" value="8,526" change="-4.1%" icon={UsersRound} tone="amber" />
        <MetricCard label="成功送达" value="12,684" change="+8.7%" icon={MailCheck} />
        <MetricCard label="召回激活" value="1,624" change="+12.3%" icon={UserRoundCheck} tone="green" />
        <MetricCard label="增量回流率" value="5.42%" change="+0.8%" icon={RotateCcw} tone="violet" />
      </div>
      <div className="page-grid">
        <Panel title="用户生命周期分布" description="规则版本 lifecycle-v3 · 每日计算">
          <div className="grid items-center gap-4 p-5 sm:grid-cols-[1fr_1.1fr]">
            <div className="h-64"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={lifecycle} dataKey="value" innerRadius={58} outerRadius={92} paddingAngle={3}>{lifecycle.map((entry) => <Cell key={entry.name} fill={entry.color} />)}</Pie><Tooltip contentStyle={chartTooltipStyle} /></PieChart></ResponsiveContainer></div>
            <div className="space-y-3">{lifecycle.map((item) => <div key={item.name} className="flex items-center justify-between rounded-xl bg-slate-50 p-3"><span className="flex items-center gap-2 text-sm text-slate-600"><span className="size-2.5 rounded-full" style={{ background: item.color }} />{item.name}</span><span className="font-semibold">{item.value.toLocaleString()}</span></div>)}</div>
          </div>
        </Panel>
        <Panel title="发送健康度" description="SES · 最近 24 小时">
          <div className="space-y-4 p-5">
            {[['送达率', '97.6%', 97.6, 'bg-emerald-500'], ['打开率', '31.8%', 31.8, 'bg-blue-500'], ['点击率', '8.6%', 8.6, 'bg-violet-500'], ['投诉率', '0.08%', 8, 'bg-red-500']].map(([label, value, width, color]) => <div key={label as string}><div className="mb-1.5 flex justify-between text-sm"><span className="text-slate-600">{label as string}</span><span className="font-semibold">{value as string}</span></div><div className="h-2 rounded-full bg-slate-100"><div className={`h-2 rounded-full ${color}`} style={{ width: `${width}%` }} /></div></div>)}
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800"><AlertOctagon className="mr-1.5 inline size-4" />投诉率接近 0.1% 预警线，系统已降低发送速率。</div>
          </div>
        </Panel>
      </div>
      <Panel title="召回活动" description="总回流与随机对照组自然回流同时展示" className="mt-5" action={<button className={secondaryButton}><Pause className="size-4" /> 紧急暂停全部</button>}>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[900px]">
            <thead><tr><th>活动</th><th>目标用户</th><th>送达率</th><th>总回流率</th><th>增量回流</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>{campaigns.map((campaign) => <tr key={campaign.name}><td className="font-medium text-slate-900">{campaign.name}</td><td>{campaign.audience.toLocaleString()}</td><td>{campaign.delivered}</td><td className="font-semibold">{campaign.returned}</td><td className="font-semibold text-emerald-700">{campaign.lift}</td><td><StatusBadge tone={campaignTone(campaign.status)}>{campaign.status}</StatusBadge></td><td><button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50">查看活动</button></td></tr>)}</tbody>
          </table>
        </div>
      </Panel>
      <div className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/70 p-4 text-sm leading-6 text-blue-800">发送前会重新计算分群快照，并排除退订、投诉、硬退信、封禁用户、频控命中用户和实验对照组。</div>
    </div>
  )
}
