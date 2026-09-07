'use client'

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleDollarSign,
  MailCheck,
  Megaphone,
  UserPlus,
  Users,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { MetricCard, PageHeader, Panel, StatusBadge, secondaryButton } from './components'

const trend = [
  { date: '08/09', newUsers: 92, activeUsers: 412 },
  { date: '08/14', newUsers: 118, activeUsers: 468 },
  { date: '08/19', newUsers: 104, activeUsers: 501 },
  { date: '08/24', newUsers: 146, activeUsers: 558 },
  { date: '08/29', newUsers: 163, activeUsers: 604 },
  { date: '09/03', newUsers: 181, activeUsers: 671 },
  { date: '09/07', newUsers: 198, activeUsers: 724 },
]

const funnel = [
  { label: '访问官网', value: 12480, rate: 100 },
  { label: '完成注册', value: 3420, rate: 27 },
  { label: '首次分析', value: 2156, rate: 17 },
  { label: '发现客户', value: 1384, rate: 11 },
  { label: '首次触达', value: 742, rate: 6 },
  { label: '购买套餐', value: 286, rate: 2.3 },
]

const alerts = [
  { title: '召回活动「30 日沉默用户」投诉率接近阈值', meta: '12 分钟前', tone: 'red' as const },
  { title: '广告 dashboard_top 有 2 个排期冲突', meta: '35 分钟前', tone: 'amber' as const },
  { title: '邀请奖励复核队列有 18 条待处理', meta: '1 小时前', tone: 'violet' as const },
]

export default function AdminOverviewPage() {
  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader
        eyebrow="Operations overview"
        title="运营总览"
        description="从获客、激活到召回，统一查看 PickGlobal 平台增长与风险。"
        action={
          <button className={secondaryButton}>
            最近 30 天
          </button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="总用户" value="38,426" change="12.8%" icon={Users} />
        <MetricCard
          label="月活用户"
          value="9,842"
          change="9.4%"
          icon={Activity}
          tone="emerald"
        />
        <MetricCard
          label="7 日激活率"
          value="63.1%"
          change="3.2%"
          icon={CheckCircle2}
          tone="violet"
        />
        <MetricCard
          label="付费转化"
          value="8.36%"
          change="0.7%"
          icon={CircleDollarSign}
          tone="amber"
        />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.55fr_1fr]">
        <Panel title="新增与活跃趋势" description="小时汇总 · 更新于 12:00">
          <div className="h-80 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ left: -16, right: 10, top: 10 }}>
                <defs>
                  <linearGradient id="activeGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.24} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis tickLine={false} axisLine={false} fontSize={12} />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }} />
                <Area
                  type="monotone"
                  dataKey="activeUsers"
                  name="活跃用户"
                  stroke="#2563eb"
                  strokeWidth={2}
                  fill="url(#activeGradient)"
                />
                <Area
                  type="monotone"
                  dataKey="newUsers"
                  name="新增用户"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="transparent"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="核心转化漏斗" description="访问官网 → 购买套餐">
          <div className="space-y-3 p-5">
            {funnel.map((step) => (
              <div key={step.label}>
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">{step.label}</span>
                  <span className="text-slate-500">
                    {step.value.toLocaleString()} · {step.rate}%
                  </span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-blue-600 to-cyan-400"
                    style={{ width: `${Math.max(step.rate, 5)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        {[
          { title: '广告贡献注册', value: '684', change: '+18.2%', icon: Megaphone, color: 'text-blue-600' },
          { title: '有效邀请', value: '326', change: '+11.6%', icon: UserPlus, color: 'text-violet-600' },
          { title: '召回激活', value: '418', change: '+7.4%', icon: MailCheck, color: 'text-emerald-600' },
        ].map((item) => (
          <div key={item.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <item.icon className={`size-5 ${item.color}`} />
              <span className="text-xs font-medium text-emerald-600">{item.change}</span>
            </div>
            <div className="mt-4 text-2xl font-bold text-slate-950">{item.value}</div>
            <div className="mt-1 text-sm text-slate-500">{item.title}</div>
          </div>
        ))}
      </div>

      <Panel
        title="待处理与风险"
        description="优先显示可能影响发送、转化和数据安全的事项"
        className="mt-5"
        action={<AlertTriangle className="size-5 text-amber-500" />}
      >
        <div className="divide-y divide-slate-100">
          {alerts.map((alert) => (
            <div key={alert.title} className="flex items-center gap-3 px-5 py-4">
              <StatusBadge tone={alert.tone}>需处理</StatusBadge>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-slate-800">{alert.title}</div>
                <div className="mt-0.5 text-xs text-slate-400">{alert.meta}</div>
              </div>
              <ArrowRight className="size-4 text-slate-400" />
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}
