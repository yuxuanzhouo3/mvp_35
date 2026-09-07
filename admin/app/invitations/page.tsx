'use client'

import { CircleDollarSign, Copy, Gift, Plus, ShieldAlert, UserCheck, UserPlus } from 'lucide-react'
import { MetricCard, PageHeader, Panel, StatusBadge, primaryButton, secondaryButton } from '../components'

const campaigns = [
  { name: '金秋出海伙伴计划', period: '09/01–09/30', invited: 1248, valid: 684, cost: '¥13,680', status: '进行中' },
  { name: '专业版老客邀请', period: '08/15–10/15', invited: 726, valid: 318, cost: '¥9,540', status: '进行中' },
  { name: '美国市场内测邀请', period: '07/01–07/31', invited: 492, valid: 201, cost: '¥4,020', status: '已结束' },
]

export default function InvitationsPage() {
  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Referral growth" title="用户邀请" description="移植 mvp_9 / mvp_25 的邀请码、分享和阶梯奖励体验，并增加奖励账本、预算控制和反作弊复核。" action={<button className={primaryButton}><Plus className="size-4" /> 新建邀请活动</button>} />
      <div className="metric-grid mb-5">
        <MetricCard label="邀请发起用户" value="2,846" change="+16.4%" icon={UserPlus} />
        <MetricCard label="有效邀请" value="1,203" change="+11.6%" icon={UserCheck} tone="green" />
        <MetricCard label="奖励成本" value="¥27,240" change="+8.3%" icon={CircleDollarSign} tone="amber" />
        <MetricCard label="待复核奖励" value="18" change="-7" icon={ShieldAlert} tone="red" />
      </div>
      <div className="page-grid">
        <Panel title="邀请转化漏斗" description="打开 → 注册 → 激活 → 有效">
          <div className="grid gap-4 p-5 sm:grid-cols-4">
            {[
              ['链接打开', '8,420', '100%'], ['完成注册', '3,268', '38.8%'],
              ['首次分析', '1,946', '23.1%'], ['有效邀请', '1,203', '14.3%'],
            ].map(([label, value, rate], index) => <div key={label} className="relative rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">0{index + 1} · {label}</div><div className="mt-3 text-xl font-bold text-slate-900">{value}</div><div className="mt-1 text-xs font-semibold text-blue-600">{rate}</div></div>)}
          </div>
        </Panel>
        <Panel title="阶梯奖励进度" description="默认阶梯可按活动修改">
          <div className="space-y-4 p-5">
            {[1, 3, 5, 10].map((level, index) => (
              <div key={level} className="flex items-center gap-3">
                <div className={`grid size-10 place-items-center rounded-full ${index < 3 ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-500'}`}><Gift className="size-4" /></div>
                <div className="flex-1"><div className="flex justify-between text-sm"><span className="font-medium">{level} 个有效邀请</span><span className="text-slate-500">{[846, 512, 284, 76][index]} 人解锁</span></div><div className="mt-2 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full bg-violet-500" style={{ width: `${[88, 65, 42, 18][index]}%` }} /></div></div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="邀请活动" description="奖励先进入 pending，确认有效后写入不可变奖励账本" className="mt-5">
        <div className="overflow-x-auto">
          <table className="data-table min-w-[820px]">
            <thead><tr><th>活动</th><th>周期</th><th>邀请注册</th><th>有效邀请</th><th>奖励成本</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>{campaigns.map((campaign) => <tr key={campaign.name}><td className="font-medium text-slate-900">{campaign.name}</td><td className="text-slate-500">{campaign.period}</td><td>{campaign.invited.toLocaleString()}</td><td className="font-semibold text-emerald-700">{campaign.valid.toLocaleString()}</td><td>{campaign.cost}</td><td><StatusBadge tone={campaign.status === '进行中' ? 'green' : 'slate'}>{campaign.status}</StatusBadge></td><td><button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50">查看详情</button></td></tr>)}</tbody>
          </table>
        </div>
      </Panel>
      <div className="mt-5 flex flex-col justify-between gap-3 rounded-2xl bg-[#10203f] p-5 text-white sm:flex-row sm:items-center"><div><div className="font-semibold">示例邀请入口</div><div className="mt-1 text-sm text-slate-300">pickgrobal.mornscience.top/invite/PG-8X4K2</div></div><button className={secondaryButton}><Copy className="size-4" /> 复制签名链接</button></div>
    </div>
  )
}
