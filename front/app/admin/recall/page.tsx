'use client'

import { Pause, Plus } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { Dialog, EmptyState, Notice, PageHeader, Panel, StatusBadge, primaryButton, secondaryButton } from '../components'

type Campaign = { id: string; name: string; status: string; audience: number; sent: boolean; created_at?: string }

const labelFor: Record<string, string> = { draft: '草稿', paused: '已暂停', active: '发送中', scheduled: '已排期', sending: '发送中' }

export default function RecallPage() {
  const [rows, setRows] = useState<Campaign[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [detail, setDetail] = useState<Campaign | null>(null)

  async function load() {
    const page = await adminApi<{ items: Campaign[] }>('/admin/recall')
    setRows(page.items)
  }

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message))
  }, [])

  async function createCampaign(event: FormEvent) {
    event.preventDefault()
    try {
      await adminApi('/admin/recall', { method: 'POST', body: JSON.stringify({ name }) })
      setOpen(false)
      setName('')
      setNotice('召回活动已保存为草稿，不会发送邮件')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建失败')
    }
  }

  async function pauseAll() {
    try {
      const result = await adminApi<{ paused: number }>('/admin/recall/pause-all', { method: 'POST' })
      setNotice(`已暂停 ${result.paused} 个活动`)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '暂停失败')
    }
  }

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="User win-back" title="用户召回" description="这是平台注册用户召回，和租户的海外线索召回分开。新建活动只保存草稿。" action={<button className={primaryButton} onClick={() => setOpen(true)}><Plus className="size-4" /> 新建召回活动</button>} />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <Panel title="召回活动" description="紧急暂停会把草稿和发送中的活动改为已暂停" action={<button className={secondaryButton} onClick={() => void pauseAll()}><Pause className="size-4" /> 紧急暂停全部</button>}>
        {rows.length === 0 ? <EmptyState query="召回" /> : (
          <div className="overflow-x-auto"><table className="data-table min-w-[760px]"><thead><tr><th>活动</th><th>目标用户</th><th>已发送</th><th>状态</th><th>操作</th></tr></thead><tbody>{rows.map((campaign) => <tr key={campaign.id}><td className="font-medium text-slate-900">{campaign.name}</td><td>{campaign.audience}</td><td>{campaign.sent ? '是' : '否'}</td><td><StatusBadge tone={campaign.status === 'paused' ? 'amber' : campaign.status === 'draft' ? 'slate' : 'green'}>{labelFor[campaign.status] || campaign.status}</StatusBadge></td><td><button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50" onClick={() => adminApi<Campaign>(`/admin/recall/${campaign.id}`).then(setDetail).catch((reason: Error) => setError(reason.message))}>查看活动</button></td></tr>)}</tbody></table></div>
        )}
      </Panel>
      {open && (
        <Dialog title="新建召回活动" onClose={() => setOpen(false)}>
          <form onSubmit={createCampaign} className="space-y-3">
            <input value={name} onChange={(event) => setName(event.target.value)} required placeholder="活动名称" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
            <button className={primaryButton} type="submit">保存草稿</button>
          </form>
        </Dialog>
      )}
      {detail && (
        <Dialog title="召回活动" onClose={() => setDetail(null)}>
          <p className="text-lg font-semibold">{detail.name}</p>
          <p className="mt-2 text-sm text-slate-500">{labelFor[detail.status] || detail.status} · 目标 {detail.audience} · {detail.sent ? '已发送' : '未发送'}</p>
          <p className="mt-2 text-xs text-slate-400">{detail.created_at}</p>
        </Dialog>
      )}
    </div>
  )
}
