'use client'

import { Copy, Plus } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { Dialog, EmptyState, Notice, PageHeader, Panel, StatusBadge, primaryButton, secondaryButton } from '../components'

type Invitation = {
  id: string
  name: string
  status: string
  invited: number
  valid: number
  reward_fen: number
  share_path: string
  created_at?: string
  invite_code?: string
}

export default function InvitationsPage() {
  const [rows, setRows] = useState<Invitation[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [created, setCreated] = useState<Invitation | null>(null)
  const [detail, setDetail] = useState<Invitation | null>(null)

  async function load() {
    const page = await adminApi<{ items: Invitation[] }>('/admin/invitations')
    setRows(page.items)
  }

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message))
  }, [])

  async function createInvitation(event: FormEvent) {
    event.preventDefault()
    try {
      const row = await adminApi<Invitation>('/admin/invitations', { method: 'POST', body: JSON.stringify({ name }) })
      setOpen(false)
      setName('')
      setCreated(row)
      setNotice('邀请活动已创建。邀请码只显示这一次。')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建失败')
    }
  }

  async function copyLink(path: string) {
    const link = `${window.location.origin}${path}`
    try {
      await navigator.clipboard.writeText(link)
      setNotice(`已复制 ${link}`)
    } catch {
      setNotice(`请手动复制 ${link}`)
    }
  }

  const latest = rows[0]

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Referral growth" title="用户邀请" description="邀请码只在创建时返回一次。复制的是活动分享路径，不是明文邀请码。" action={<button className={primaryButton} onClick={() => setOpen(true)}><Plus className="size-4" /> 新建邀请活动</button>} />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <Panel title="邀请活动" description="奖励仍是草稿，不会自动入账">
        {rows.length === 0 ? <EmptyState query="邀请" /> : (
          <div className="overflow-x-auto"><table className="data-table min-w-[820px]"><thead><tr><th>活动</th><th>创建时间</th><th>邀请注册</th><th>有效邀请</th><th>奖励（分）</th><th>状态</th><th>操作</th></tr></thead><tbody>{rows.map((campaign) => <tr key={campaign.id}><td className="font-medium text-slate-900">{campaign.name}</td><td className="text-slate-500">{campaign.created_at}</td><td>{campaign.invited}</td><td>{campaign.valid}</td><td>{campaign.reward_fen}</td><td><StatusBadge tone={campaign.status === 'draft' ? 'slate' : 'green'}>{campaign.status === 'draft' ? '草稿' : campaign.status}</StatusBadge></td><td><button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50" onClick={() => adminApi<Invitation>(`/admin/invitations/${campaign.id}`).then(setDetail).catch((reason: Error) => setError(reason.message))}>查看详情</button></td></tr>)}</tbody></table></div>
        )}
      </Panel>
      <div className="mt-5 flex flex-col justify-between gap-3 rounded-2xl bg-[#10203f] p-5 text-white sm:flex-row sm:items-center">
        <div><div className="font-semibold">最新邀请入口</div><div className="mt-1 text-sm text-slate-300">{latest ? latest.share_path : '还没有邀请活动'}</div></div>
        <button className={secondaryButton} onClick={() => latest ? void copyLink(latest.share_path) : setError('请先新建邀请活动')}><Copy className="size-4" /> 复制签名链接</button>
      </div>
      {open && (
        <Dialog title="新建邀请活动" onClose={() => setOpen(false)}>
          <form onSubmit={createInvitation} className="space-y-3">
            <input value={name} onChange={(event) => setName(event.target.value)} required placeholder="活动名称" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
            <button className={primaryButton} type="submit">创建</button>
          </form>
        </Dialog>
      )}
      {created && (
        <Dialog title="邀请码" onClose={() => setCreated(null)}>
          <p className="font-mono text-lg">{created.invite_code}</p>
          <p className="mt-2 text-sm text-slate-500">分享路径 {created.share_path}</p>
          <button className={`${secondaryButton} mt-4`} onClick={() => void copyLink(created.share_path)}>复制链接</button>
        </Dialog>
      )}
      {detail && (
        <Dialog title="邀请详情" onClose={() => setDetail(null)}>
          <p className="text-lg font-semibold">{detail.name}</p>
          <p className="mt-2 text-sm text-slate-500">{detail.share_path} · 注册 {detail.invited} · 有效 {detail.valid}</p>
          <button className={`${secondaryButton} mt-4`} onClick={() => void copyLink(detail.share_path)}>复制链接</button>
        </Dialog>
      )}
    </div>
  )
}
