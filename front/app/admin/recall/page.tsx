'use client'

import { Pause, Plus } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { Dialog, EmptyState, Notice, PageHeader, Panel, StatusBadge, primaryButton, secondaryButton } from '../components'

type Campaign = { id: string; name: string; status: string; audience: number; sent: boolean; created_at?: string }
type SilentUser = { id: string; name: string; email_masked?: string | null; absent_days: number; month_logins: number }
type RecallLink = { id: string; name: string; share_path: string; bucket: number; used_at?: string | null }
type Audience = { today: string; daily_logins: number; monthly_logins: number; buckets: Record<string, SilentUser[]> }

const labelFor: Record<string, string> = { draft: '草稿', paused: '已暂停', active: '发送中', scheduled: '已排期', sending: '发送中' }

export default function RecallPage() {
  const [rows, setRows] = useState<Campaign[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [detail, setDetail] = useState<Campaign | null>(null)
  const [audience, setAudience] = useState<Audience | null>(null)
  const [links, setLinks] = useState<RecallLink[]>([])

  async function load() {
    const page = await adminApi<{ items: Campaign[] }>('/admin/recall')
    setRows(page.items)
    const counted = await adminApi<Audience>('/admin/recall/audience')
    setAudience(counted)
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

  async function makeLinks(days: number) {
    try {
      const result = await adminApi<{ items: RecallLink[] }>('/admin/recall/links', { method: 'POST', body: JSON.stringify({ days }) })
      setLinks(result.items)
      setNotice(`已生成 ${result.items.length} 条 ${days} 天未登录召回链接`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '生成失败')
    }
  }

  async function copyLink(path: string) {
    const link = `${window.location.origin}${path}`
    try {
      await navigator.clipboard.writeText(link)
      setNotice(`已复制 ${link}`)
    } catch {
      setNotice(link)
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
      <PageHeader eyebrow="User win-back" title="用户召回" description="统计当日登录和当月登录。未登录满 7、14、30 天的用户可以生成召回链接。用户从链接登录后获得 10% 优惠券。连续登录满 7 天给 1 次抽奖，满 14 天再给 2 次，满 30 天奖励现金。" action={<button className={primaryButton} onClick={() => setOpen(true)}><Plus className="size-4" /> 新建召回活动</button>} />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs text-slate-500">今日登录</p><p className="mt-2 text-2xl font-semibold">{audience?.daily_logins ?? '—'}</p></article>
        <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs text-slate-500">本月有登录</p><p className="mt-2 text-2xl font-semibold">{audience?.monthly_logins ?? '—'}</p></article>
        <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs text-slate-500">统计日</p><p className="mt-2 text-2xl font-semibold">{audience?.today ?? '—'}</p></article>
      </div>
      {([7, 14, 30] as const).map((days) => {
        const people = audience?.buckets[String(days)] || []
        return (
          <Panel key={days} title={`${days} 天未登录`} description={`${people.length} 人`} className="mb-5" action={<button className={secondaryButton} onClick={() => void makeLinks(days)}>生成召回链接</button>}>
            {people.length === 0 ? <EmptyState query={`${days} 天未登录`} /> : (
              <div className="overflow-x-auto"><table className="data-table min-w-[640px]"><thead><tr><th>用户</th><th>未登录天数</th><th>本月登录天数</th></tr></thead><tbody>{people.map((person) => <tr key={person.id}><td className="font-medium text-slate-900">{person.name}<div className="text-xs text-slate-500">{person.email_masked}</div></td><td>{person.absent_days}</td><td>{person.month_logins}</td></tr>)}</tbody></table></div>
            )}
          </Panel>
        )
      })}
      {links.length > 0 && (
        <Panel title="召回链接" description="复制后发给对应用户。对方登录后获得优惠券。" className="mb-5">
          <div className="overflow-x-auto"><table className="data-table min-w-[720px]"><thead><tr><th>用户</th><th>天数</th><th>链接</th><th></th></tr></thead><tbody>{links.map((link) => <tr key={link.id}><td>{link.name}</td><td>{link.bucket}</td><td className="font-mono text-xs">{link.share_path}</td><td><button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50" onClick={() => void copyLink(link.share_path)}>复制</button></td></tr>)}</tbody></table></div>
        </Panel>
      )}
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
