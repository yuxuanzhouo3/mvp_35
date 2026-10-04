'use client'

import { Eye, Image as ImageIcon, MoreHorizontal, Plus, Video } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import {
  Dialog,
  EmptyState,
  FilterBar,
  Notice,
  PageHeader,
  Panel,
  Select,
  StatusBadge,
  primaryButton,
  secondaryButton,
} from '../components'

type Ad = {
  id: string
  title: string
  placement: string
  media_type: string
  status: string
  link_url?: string
  ctr: string
  conversions: number
}

const placements = [
  ['home_mid_banner', '官网中部'],
  ['pricing_banner', '官网底部'],
  ['dashboard_top', '工作台顶部'],
  ['report_footer', '报告页底部'],
  ['copilot_sidebar', '对话侧栏'],
]

const labelFor: Record<string, string> = { draft: '草稿', active: '投放中', paused: '已暂停', ended: '已结束' }
const toneFor = (status: string) => {
  if (status === 'active') return 'green' as const
  if (status === 'paused') return 'amber' as const
  if (status === 'ended') return 'violet' as const
  if (status === 'draft') return 'slate' as const
  return 'blue' as const
}

export default function AdsPage() {
  const [ads, setAds] = useState<Ad[]>([])
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [creating, setCreating] = useState(false)
  const [library, setLibrary] = useState<Ad[] | null>(null)
  const [preview, setPreview] = useState<Ad | null>(null)
  const [menuId, setMenuId] = useState('')
  const [title, setTitle] = useState('')
  const [placement, setPlacement] = useState('home_mid_banner')
  const [mediaType, setMediaType] = useState('image')
  const [publishAd, setPublishAd] = useState<Ad | null>(null)
  const [publishLink, setPublishLink] = useState('')

  async function load() {
    const page = await adminApi<{ items: Ad[] }>('/admin/ads')
    setAds(page.items)
  }

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message))
  }, [])

  const filtered = useMemo(
    () => ads.filter((ad) => (status === 'all' || ad.status === status) && `${ad.title} ${ad.id} ${ad.placement}`.toLowerCase().includes(search.toLowerCase())),
    [ads, search, status],
  )

  async function createAd(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await adminApi('/admin/ads', { method: 'POST', body: JSON.stringify({ title, placement, media_type: mediaType }) })
      setCreating(false)
      setTitle('')
      setNotice('广告已保存为草稿')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建失败')
    }
  }

  async function setAdStatus(ad: Ad, next: string) {
    setMenuId('')
    try {
      await adminApi(`/admin/ads/${ad.id}/status`, { method: 'POST', body: JSON.stringify({ status: next }) })
      setNotice(`${ad.title} 已更新为${labelFor[next] || next}`)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '更新失败')
    }
  }

  async function publishAdLive(event: FormEvent) {
    event.preventDefault()
    if (!publishAd) return
    setError('')
    try {
      await adminApi(`/admin/ads/${publishAd.id}/status`, { method: 'POST', body: JSON.stringify({ status: 'active', link_url: publishLink }) })
      setNotice(`${publishAd.title} 已上架，点击后打开客户网站`)
      setPublishAd(null)
      setPublishLink('')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '上架失败')
    }
  }

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Ad operations" title="广告管理" description="选择广告位后，在广告投放上架里填写客户的广告网站链接，再点击上架。官网、工作台和报告页都会显示，手机同样可见。" action={<button className={primaryButton} onClick={() => setCreating(true)}><Plus className="size-4" /> 新建广告活动</button>} />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <FilterBar search={search} onSearch={setSearch} placeholder="搜索广告名称、ID 或广告位">
        <Select value={status} onChange={setStatus} label="广告状态">
          <option value="all">全部状态</option>
          <option value="active">投放中</option>
          <option value="draft">草稿</option>
          <option value="paused">已暂停</option>
          <option value="ended">已结束</option>
        </Select>
        <button className={secondaryButton} onClick={() => adminApi<{ items: Ad[] }>('/admin/ads/creatives').then((page) => setLibrary(page.items)).catch((reason: Error) => setError(reason.message))}>素材库</button>
      </FilterBar>
      {library && (
        <Panel title="素材库" description={`${library.length} 条素材`} className="mb-5" action={<button className={secondaryButton} onClick={() => setLibrary(null)}>收起</button>}>
          {library.length === 0 ? <EmptyState query="素材" /> : (
            <ul className="divide-y divide-slate-100">{library.map((item) => <li key={item.id} className="flex items-center justify-between px-5 py-3 text-sm"><span>{item.title} · {item.media_type === 'video' ? '视频' : '图片'}</span><span className="font-mono text-xs text-slate-400">{item.placement}</span></li>)}</ul>
          )}
        </Panel>
      )}
      <Panel title="广告活动" description={`找到 ${filtered.length} 条活动`}>
        {filtered.length === 0 ? <EmptyState query={search || '广告'} /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">广告</th>
                  <th className="px-4 py-3 font-semibold">广告位</th>
                  <th className="px-4 py-3 font-semibold">状态</th>
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
                        <div className="grid size-12 place-items-center rounded-xl bg-gradient-to-br from-blue-100 to-cyan-50 text-blue-600">{ad.media_type === 'video' ? <Video className="size-5" /> : <ImageIcon className="size-5" />}</div>
                        <div><div className="font-medium text-slate-900">{ad.title}</div><div className="mt-0.5 text-xs text-slate-400">{ad.id}</div></div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-xs text-slate-600">{placements.find(([value]) => value === ad.placement)?.[1] || ad.placement}</td>
                    <td className="px-4 py-4"><StatusBadge tone={toneFor(ad.status)}>{labelFor[ad.status] || ad.status}</StatusBadge></td>
                    <td className="px-4 py-4 font-medium text-slate-800">{ad.ctr}</td>
                    <td className="px-4 py-4 text-slate-600">{ad.conversions.toLocaleString()}</td>
                    <td className="relative px-4 py-4">
                      <div className="flex items-center gap-1">
                        <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`预览 ${ad.title}`} onClick={() => adminApi<Ad>(`/admin/ads/${ad.id}`).then(setPreview).catch((reason: Error) => setError(reason.message))}><Eye className="size-4" /></button>
                        <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`更多 ${ad.title}`} onClick={() => setMenuId(menuId === ad.id ? '' : ad.id)}><MoreHorizontal className="size-4" /></button>
                      </div>
                      {menuId === ad.id && (
                        <div className="absolute right-4 z-10 mt-1 w-36 rounded-xl border border-slate-200 bg-white p-1 shadow-lg">
                          <button className="block w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => { setMenuId(''); setPublishAd(ad); setPublishLink(ad.link_url || '') }}>上架</button>
                          <button className="block w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => void setAdStatus(ad, 'paused')}>暂停</button>
                          <button className="block w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => void setAdStatus(ad, 'ended')}>结束</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {creating && (
        <Dialog title="新建广告活动" onClose={() => setCreating(false)}>
          <form onSubmit={createAd} className="space-y-3">
            <input value={title} onChange={(event) => setTitle(event.target.value)} required placeholder="广告名称" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
            <Select value={placement} onChange={setPlacement} label="广告位">
              {placements.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Select>
            <Select value={mediaType} onChange={setMediaType} label="素材类型">
              <option value="image">图片</option>
              <option value="video">视频</option>
            </Select>
            <button className={primaryButton} type="submit">保存草稿</button>
          </form>
        </Dialog>
      )}
      {preview && (
        <Dialog title="广告预览" onClose={() => setPreview(null)}>
          <p className="text-lg font-semibold text-slate-950">{preview.title}</p>
          <p className="mt-2 text-sm text-slate-500">{placements.find(([value]) => value === preview.placement)?.[1] || preview.placement} · {preview.media_type === 'video' ? '视频' : '图片'} · {labelFor[preview.status] || preview.status}</p>
          <p className="mt-4 text-sm text-slate-600">CTR {preview.ctr} · 目标转化 {preview.conversions}</p>
          {preview.link_url && <p className="mt-2 break-all text-sm text-slate-500">{preview.link_url}</p>}
        </Dialog>
      )}
      {publishAd && (
        <Dialog title="广告投放上架" onClose={() => setPublishAd(null)}>
          <form onSubmit={publishAdLive} className="space-y-3">
            <p className="text-sm text-slate-600">{publishAd.title} 将出现在{placements.find(([value]) => value === publishAd.placement)?.[1] || '所选位置'}。手机和电脑都使用这个位置。</p>
            <label className="block text-sm font-medium text-slate-700" htmlFor="ad-website">广告网站链接</label>
            <input id="ad-website" value={publishLink} onChange={(event) => setPublishLink(event.target.value)} required placeholder="https://customer.com" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
            <p className="text-xs text-slate-500">填写客户的广告网站。点击广告会打开这个网址，不会打开本站登录页。</p>
            <button className={primaryButton} type="submit">上架</button>
          </form>
        </Dialog>
      )}
    </div>
  )
}
