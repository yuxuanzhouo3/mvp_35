'use client'

import { Ban, Clock3, Download, MoreHorizontal, ShieldAlert, UserCheck, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { EmptyState, FilterBar, MetricCard, PageHeader, Panel, StatusBadge, secondaryButton, selectClass } from '../components'

const users = [
  { id: 'USR-8F2A91', name: '深圳华跃科技', email: 'li***@huayue.cn', plan: '专业版', source: '自然搜索', stage: '活跃', lastActive: '4 分钟前', created: '2026-08-02' },
  { id: 'USR-7BC114', name: '宁波澜海贸易', email: 'zh***@lanhai.com', plan: '免费版', source: '用户邀请', stage: '已激活', lastActive: '2 小时前', created: '2026-08-18' },
  { id: 'USR-68AD32', name: '广州原点品牌', email: 'ma***@origin.cn', plan: '企业版', source: '广告', stage: '活跃', lastActive: '昨天', created: '2026-06-21' },
  { id: 'USR-54A9D0', name: '杭州山谷家居', email: 'wa***@valley.cn', plan: '免费版', source: '用户邀请', stage: '流失风险', lastActive: '18 天前', created: '2026-05-14' },
  { id: 'USR-41CE88', name: '厦门逐浪供应链', email: 'ch***@wave.com', plan: '专业版', source: '直接访问', stage: '沉默', lastActive: '9 天前', created: '2026-04-07' },
]

function stageTone(stage: string) {
  if (stage === '活跃') return 'green' as const
  if (stage === '已激活') return 'blue' as const
  if (stage === '流失风险') return 'red' as const
  return 'amber' as const
}

export default function UsersPage() {
  const [query, setQuery] = useState('')
  const [stage, setStage] = useState('全部阶段')
  const filtered = useMemo(() => users.filter((user) =>
    (stage === '全部阶段' || user.stage === stage) &&
    `${user.id} ${user.name} ${user.email}`.toLowerCase().includes(query.toLowerCase())), [query, stage])

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="User intelligence" title="用户数据管理" description="参考 mvp_1 的用户列表和统一画像，将账号、企业、行为、邀请和召回信息汇集到用户 360° 视图。" action={<button className={secondaryButton}><Download className="size-4" /> 安全导出</button>} />
      <div className="metric-grid mb-5">
        <MetricCard label="平台用户" value="38,426" change="+12.8%" icon={Users} />
        <MetricCard label="近 7 日新增" value="1,284" change="+8.4%" icon={UserCheck} tone="green" />
        <MetricCard label="流失风险" value="2,146" change="-3.1%" icon={Clock3} tone="amber" />
        <MetricCard label="风险账号" value="73" change="+6" icon={ShieldAlert} tone="red" />
      </div>
      <FilterBar value={query} onChange={setQuery} placeholder="搜索用户 ID、企业或脱敏邮箱">
        <select className={selectClass} value={stage} onChange={(event) => setStage(event.target.value)} aria-label="生命周期阶段">
          {['全部阶段', '活跃', '已激活', '沉默', '流失风险'].map((item) => <option key={item}>{item}</option>)}
        </select>
        <select className={selectClass} aria-label="套餐"><option>全部套餐</option><option>免费版</option><option>专业版</option><option>企业版</option></select>
        <button className={secondaryButton}>保存为分群</button>
      </FilterBar>
      <Panel title="用户列表" description={`找到 ${filtered.length} 位用户 · 默认隐藏敏感信息`}>
        {filtered.length === 0 ? <EmptyState query={query} /> : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[1040px]">
              <thead><tr><th>用户</th><th>套餐</th><th>来源</th><th>生命周期</th><th>最近活跃</th><th>注册日期</th><th>操作</th></tr></thead>
              <tbody>
                {filtered.map((user) => (
                  <tr key={user.id}>
                    <td><div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-full bg-blue-50 text-xs font-bold text-blue-700">{user.name.slice(0, 2)}</div><div><div className="font-medium text-slate-900">{user.name}</div><div className="mt-0.5 text-xs text-slate-400">{user.email} · {user.id}</div></div></div></td>
                    <td><StatusBadge tone={user.plan === '企业版' ? 'violet' : user.plan === '专业版' ? 'blue' : 'slate'}>{user.plan}</StatusBadge></td>
                    <td className="text-slate-600">{user.source}</td><td><StatusBadge tone={stageTone(user.stage)}>{user.stage}</StatusBadge></td>
                    <td className="text-slate-600">{user.lastActive}</td><td className="text-slate-500">{user.created}</td>
                    <td><div className="flex gap-1"><button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50">查看 360°</button><button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`管理 ${user.name}`}><MoreHorizontal className="size-4" /></button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-xs text-slate-400"><span>敏感字段查看和导出均写入审计日志</span><span>1–{filtered.length} / 38,426</span></div>
      </Panel>
      <div className="mt-5 rounded-2xl border border-red-100 bg-red-50/60 p-4 text-sm text-red-700"><Ban className="mr-2 inline size-4" />封禁、删除、额度调整等高风险动作仅在用户详情中执行，并要求填写原因。</div>
    </div>
  )
}
