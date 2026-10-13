'use client'

import { Copy, Plus } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { Dialog, EmptyState, Notice, PageHeader, Panel, StatusBadge, primaryButton, secondaryButton } from '../components'

type InvitePerson = { id: string; name: string; email_masked?: string | null; via_name?: string }
type InviteEvent = {
  invitee_name: string
  link: string
  invited_at?: string | null
  paid_at?: string | null
  paid_fen: number
  reward_fen: number
}
type CashRequest = { id: string; kind?: string; amount_fen: number; status: string; due_at?: string | null }
type Payout = {
  invitor_id: string
  invitor_name: string
  email_masked?: string | null
  invite_code: string
  used_by: InvitePerson[]
  invited_later: InvitePerson[]
  paid_fen: number
  owed_fen: number
  discount_fen: number
  events: InviteEvent[]
  cash_requests: CashRequest[]
}

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
  const [payouts, setPayouts] = useState<Payout[]>([])

  function yuan(fen: number) {
    return `¥${(fen / 100).toFixed(2)}`
  }

  async function load() {
    const page = await adminApi<{ items: Invitation[] }>('/admin/invitations')
    setRows(page.items)
    const owed = await adminApi<{ items: Payout[] }>('/admin/invitations/payouts')
    setPayouts(owed.items)
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

  async function markPaid(payoutId: string) {
    try {
      await adminApi(`/admin/invitations/payouts/${payoutId}/paid`, { method: 'POST' })
      setNotice('已记为打款完成')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '更新失败')
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
      <PageHeader eyebrow="Referral growth" title="用户邀请" description="A 在日期 D 用链接 C 邀请 B。B 在日期 E 购买会员金额 F 后，A 获得 10% 奖励 G。奖励先留作账户优惠；A 在账户里申请兑现后，5 个工作日内打现金。" action={<button className={primaryButton} onClick={() => setOpen(true)}><Plus className="size-4" /> 新建邀请活动</button>} />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <Panel title="邀请活动" description="奖励仍是草稿，不会自动入账">
        {rows.length === 0 ? <EmptyState query="邀请" /> : (
          <div className="overflow-x-auto"><table className="data-table min-w-[820px]"><thead><tr><th>活动</th><th>创建时间</th><th>邀请注册</th><th>有效邀请</th><th>奖励（分）</th><th>状态</th><th>操作</th></tr></thead><tbody>{rows.map((campaign) => <tr key={campaign.id}><td className="font-medium text-slate-900">{campaign.name}</td><td className="text-slate-500">{campaign.created_at}</td><td>{campaign.invited}</td><td>{campaign.valid}</td><td>{campaign.reward_fen}</td><td><StatusBadge tone={campaign.status === 'draft' ? 'slate' : 'green'}>{campaign.status === 'draft' ? '草稿' : campaign.status}</StatusBadge></td><td><button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50" onClick={() => adminApi<Invitation>(`/admin/invitations/${campaign.id}`).then(setDetail).catch((reason: Error) => setError(reason.message))}>查看详情</button></td></tr>)}</tbody></table></div>
        )}
      </Panel>
      <Panel title="邀请人与应付" description="应付是被邀请人已付会员金额的 10%。未申请兑现的部分记为账户优惠。">
        {payouts.length === 0 ? <EmptyState query="邀请关系" /> : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[820px]">
              <thead><tr><th>邀请人</th><th>邀请码</th><th>使用了链接的人</th><th>后来邀请的人</th><th>已入账</th><th>奖励</th><th>账户优惠</th><th>兑现</th></tr></thead>
              <tbody>
                {payouts.map((row) => (
                  <tr key={row.invitor_id}>
                    <td className="font-medium text-slate-900">{row.invitor_name}<div className="text-xs text-slate-500">{row.email_masked}</div></td>
                    <td className="font-mono text-xs">{row.invite_code}</td>
                    <td>{row.used_by.map((person) => person.name || person.email_masked).join('、') || '—'}</td>
                    <td>{row.invited_later.map((person) => `${person.name || person.email_masked}（经 ${person.via_name}）`).join('、') || '—'}</td>
                    <td>{yuan(row.paid_fen)}</td>
                    <td>{yuan(row.owed_fen)}</td>
                    <td>{yuan(row.discount_fen)}</td>
                    <td className="text-xs">
                      {row.cash_requests.length === 0 ? '—' : row.cash_requests.map((item) => (
                        <div key={item.id} className="flex items-center gap-2 py-1">
                          <span>{yuan(item.amount_fen)} {item.status === 'paid' ? '已打款' : `待打款 ${item.due_at?.slice(0, 10) || ''}`}</span>
                          {item.status !== 'paid' && <button className="rounded-lg px-2 py-1 font-semibold text-blue-600 hover:bg-blue-50" onClick={() => void markPaid(item.id)}>标记已打款</button>}
                        </div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <Panel title="邀请明细" description="每一行是一次邀请和对应的会员付款。">
        {payouts.every((row) => row.events.length === 0) ? <EmptyState query="邀请明细" /> : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[980px]">
              <thead><tr><th>邀请人 A</th><th>链接 C</th><th>邀请日 D</th><th>被邀请人 B</th><th>付费日 E</th><th>付费 F</th><th>奖励 G</th></tr></thead>
              <tbody>
                {payouts.flatMap((row) => row.events.map((event) => (
                  <tr key={`${row.invitor_id}-${event.invitee_name}-${event.paid_at || 'none'}`}>
                    <td className="font-medium text-slate-900">{row.invitor_name}</td>
                    <td className="font-mono text-xs">{event.link}</td>
                    <td>{event.invited_at?.slice(0, 10) || '—'}</td>
                    <td>{event.invitee_name || '—'}</td>
                    <td>{event.paid_at?.slice(0, 10) || '—'}</td>
                    <td>{yuan(event.paid_fen)}</td>
                    <td>{yuan(event.reward_fen)}</td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
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
