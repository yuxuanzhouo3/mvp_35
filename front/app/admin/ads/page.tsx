'use client'

import { Eye, Image as ImageIcon, MoreHorizontal, Plus, Video } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  FilterBar,
  PageHeader,
  Panel,
  Select,
  StatusBadge,
  primaryButton,
  secondaryButton,
} from '../components'

const ads = [
  { id: 'AD-24091', title: '美国市场分析季', placement: 'dashboard_top', type: '图片', status: '投放中', ctr: '4.82%', conversions: 286, priority: 90 },
  { id: 'AD-24087', title: '专业版限时体验', placement: 'pricing_banner', type: '视频', status: '已排期', ctr: '—', conversions: 0, priority: 80 },
  { id: 'AD-24072', title: 'AI 客户发现升级', placement: 'copilot_sidebar', type: '图片', status: '草稿', ctr: '—', conversions: 0, priority: 50 },
  { id: 'AD-24061', title: '跨境增长白皮书', placement: 'home_mid_banner', type: '图片', status: '已暂停', ctr: '2.36%', conversions: 94, priority: 60 },
  { id: 'AD-24033', title: '九月会员权益', placement: 'report_footer', type: '视频', status: '已结束', ctr: '3.14%', conversions: 173, priority: 70 },
]

const toneForStatus = (status: string) => {
  if (status === '投放中') return 'green' as const
  if (status === '已排期') return 'blue' as const
  if (status === '草稿') return 'slate' as const
  if (status === '已暂停') return 'amber' as const
  return 'violet' as const
}

export default function AdsPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const filtered = useMemo(
    () =>
      ads.filter(
        (ad) =>
          (status === 'all' || ad.status === status) &&
          `${ad.title} ${ad.id} ${ad.placement}`.toLowerCase().includes(search.toLowerCase()),
      ),
    [search, status],
  )

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader
        eyebrow="Ad operations"
        title="广告管理"
        description="管理 PickGlobal 自有流量广告位、素材、定向和增量转化。"
        action={
          <button className={primaryButton}>
            <Plus className="size-4" /> 新建广告活动
          </button>
        }
      />
      <FilterBar search={search} onSearch={setSearch} placeholder="搜索广告名称、ID 或广告位">
        <Select value={status} onChange={setStatus} label="广告状态">
          <option value="all">全部状态</option>
          <option value="投放中">投放中</option>
          <option value="已排期">已排期</option>
          <option value="草稿">草稿</option>
          <option value="已暂停">已暂停</option>
          <option value="已结束">已结束</option>
        </Select>
        <button className={secondaryButton}>素材库</button>
      </FilterBar>

      <Panel title="广告活动" description={`找到 ${filtered.length} 条活动 · 数据更新于 12:00`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 font-semibold">广告</th>
                <th className="px-4 py-3 font-semibold">广告位</th>
                <th className="px-4 py-3 font-semibold">状态</th>
                <th className="px-4 py-3 font-semibold">优先级</th>
                <th className="px-4 py-3 font-semibold">CTR</th>
                <th className="px-4 py-3 font-semibold">目标转化</th>
                <th className="px-4 py-3 font-semibold">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((ad) => (
                <tr key={ad.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="grid size-12 place-items-center rounded-xl bg-gradient-to-br from-blue-100 to-cyan-50 text-blue-600">
                        {ad.type === '视频' ? <Video className="size-5" /> : <ImageIcon className="size-5" />}
                      </div>
                      <div>
                        <div className="font-medium text-slate-900">{ad.title}</div>
                        <div className="mt-0.5 text-xs text-slate-400">{ad.id} · {ad.type}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 font-mono text-xs text-slate-600">{ad.placement}</td>
                  <td className="px-4 py-4"><StatusBadge tone={toneForStatus(ad.status)}>{ad.status}</StatusBadge></td>
                  <td className="px-4 py-4 text-slate-600">{ad.priority}</td>
                  <td className="px-4 py-4 font-medium text-slate-800">{ad.ctr}</td>
                  <td className="px-4 py-4 text-slate-600">{ad.conversions.toLocaleString()}</td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-1">
                      <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`预览 ${ad.title}`}>
                        <Eye className="size-4" />
                      </button>
                      <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`更多 ${ad.title}`}>
                        <MoreHorizontal className="size-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}
