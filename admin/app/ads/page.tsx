'use client'

import { Eye, Image as ImageIcon, MoreHorizontal, MousePointerClick, Plus, Target, Video } from 'lucide-react'
import { useMemo, useState } from 'react'
import { EmptyState, FilterBar, MetricCard, PageHeader, Panel, StatusBadge, primaryButton, secondaryButton, selectClass } from '../components'

const ads = [
  { id: 'AD-24091', title: '美国市场分析季', placement: 'dashboard_top', type: '图片', status: '投放中', ctr: '4.82%', conversions: 286, priority: 90 },
  { id: 'AD-24087', title: '专业版限时体验', placement: 'pricing_banner', type: '视频', status: '已排期', ctr: '—', conversions: 0, priority: 80 },
  { id: 'AD-24072', title: 'AI 客户发现升级', placement: 'copilot_sidebar', type: '图片', status: '草稿', ctr: '—', conversions: 0, priority: 50 },
  { id: 'AD-24061', title: '跨境增长白皮书', placement: 'home_mid_banner', type: '图片', status: '已暂停', ctr: '2.36%', conversions: 94, priority: 60 },
  { id: 'AD-24033', title: '九月会员权益', placement: 'report_footer', type: '视频', status: '已结束', ctr: '3.14%', conversions: 173, priority: 70 },
]

function tone(status: string) {
  if (status === '投放中') return 'green' as const
  if (status === '已排期') return 'blue' as const
  if (status === '已暂停') return 'amber' as const
  if (status === '已结束') return 'violet' as const
  return 'slate' as const
}

export default function AdsPage() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('全部状态')
  const filtered = useMemo(() => ads.filter((ad) =>
    (status === '全部状态' || ad.status === status) &&
    `${ad.id} ${ad.title} ${ad.placement}`.toLowerCase().includes(query.toLowerCase())), [query, status])

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Ad operations" title="广告管理" description="整合 mvp_28 的素材预览、筛选、优先级和上下架体验，并增加活动审批、定向与转化归因。" action={<button className={primaryButton}><Plus className="size-4" /> 新建广告活动</button>} />
      <div className="metric-grid mb-5">
        <MetricCard label="广告曝光" value="1.28M" change="+14.8%" icon={Eye} />
        <MetricCard label="广告点击" value="48,962" change="+9.3%" icon={MousePointerClick} tone="violet" />
        <MetricCard label="平均 CTR" value="3.82%" change="-0.2%" icon={Target} tone="amber" />
        <MetricCard label="贡献注册" value="684" change="+18.2%" icon={Target} tone="green" />
      </div>
      <FilterBar value={query} onChange={setQuery} placeholder="搜索广告名称、ID 或广告位">
        <select className={selectClass} value={status} onChange={(event) => setStatus(event.target.value)} aria-label="广告状态">
          {['全部状态', '投放中', '已排期', '草稿', '已暂停', '已结束'].map((item) => <option key={item}>{item}</option>)}
        </select>
        <button className={secondaryButton}>素材库</button>
        <button className={secondaryButton}>广告位</button>
      </FilterBar>
      <Panel title="广告活动" description={`找到 ${filtered.length} 条活动 · 小时汇总`}>
        {filtered.length === 0 ? <EmptyState query={query} /> : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[900px]">
              <thead><tr><th>广告</th><th>广告位</th><th>状态</th><th>优先级</th><th>CTR</th><th>目标转化</th><th>操作</th></tr></thead>
              <tbody>
                {filtered.map((ad) => (
                  <tr key={ad.id}>
                    <td><div className="flex items-center gap-3"><div className="grid size-11 place-items-center rounded-xl bg-gradient-to-br from-blue-100 to-cyan-50 text-blue-600">{ad.type === '视频' ? <Video className="size-5" /> : <ImageIcon className="size-5" />}</div><div><div className="font-medium text-slate-900">{ad.title}</div><div className="mt-0.5 text-xs text-slate-400">{ad.id} · {ad.type}</div></div></div></td>
                    <td className="font-mono text-xs text-slate-600">{ad.placement}</td>
                    <td><StatusBadge tone={tone(ad.status)}>{ad.status}</StatusBadge></td>
                    <td className="text-slate-600">{ad.priority}</td><td className="font-semibold text-slate-800">{ad.ctr}</td><td>{ad.conversions.toLocaleString()}</td>
                    <td><div className="flex gap-1"><button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`预览 ${ad.title}`}><Eye className="size-4" /></button><button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`更多 ${ad.title}`}><MoreHorizontal className="size-4" /></button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}
