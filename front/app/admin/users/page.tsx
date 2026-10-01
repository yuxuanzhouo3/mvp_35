'use client'

import { Ban, Clock3, Download, MoreHorizontal, ShieldAlert, UserCheck, Users } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { adminApi, downloadText } from '@/lib/admin-session'
import { Dialog, EmptyState, FilterBar, MetricCard, Notice, PageHeader, Panel, StatusBadge, secondaryButton, selectClass } from '../components'

type UserRow = {
  id: string
  display_name: string | null
  email_masked: string | null
  plan_id?: string
  status: string
  role?: string
  created_at?: string
  updated_at?: string
}

type UserDetail = UserRow & { username?: string | null; recent_audit: Array<{ action: string; created_at?: string }> }
type Segment = { id: string; name: string; matched: number; stage?: string }

export default function UsersPage() {
  const [users, setUsers] = useState<UserRow[]>([])
  const [summary, setSummary] = useState({ users: 0, suspended: 0, active: 0 })
  const [segments, setSegments] = useState<Segment[]>([])
  const [query, setQuery] = useState('')
  const [stage, setStage] = useState('全部阶段')
  const [plan, setPlan] = useState('全部套餐')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [detail, setDetail] = useState<UserDetail | null>(null)
  const [manage, setManage] = useState<UserRow | null>(null)
  const [reason, setReason] = useState('')
  const [segmentOpen, setSegmentOpen] = useState(false)
  const [segmentName, setSegmentName] = useState('')

  async function load() {
    const [list, counts, saved] = await Promise.all([
      adminApi<{ items: UserRow[] }>('/admin/users'),
      adminApi<typeof summary>('/admin/users/summary'),
      adminApi<{ items: Segment[] }>('/admin/segments'),
    ])
    setUsers(list.items)
    setSummary(counts)
    setSegments(saved.items)
  }

  useEffect(() => {
    load().catch((reasonText: Error) => setError(reasonText.message))
  }, [])

  const filtered = useMemo(() => users.filter((user) => {
    const stageOk = stage === '全部阶段' || (stage === '已停用' ? user.status === 'suspended' : user.status !== 'suspended')
    const planOk = plan === '全部套餐' || user.plan_id === plan
    const text = `${user.id} ${user.display_name || ''} ${user.email_masked || ''}`.toLowerCase()
    return stageOk && planOk && text.includes(query.toLowerCase())
  }), [users, query, stage, plan])

  async function exportUsers() {
    setError('')
    try {
      const file = await adminApi<{ filename: string; body: string }>('/admin/users/export', { method: 'POST' })
      downloadText(file.filename, file.body)
      setNotice('用户名单已导出，并写入审计日志')
    } catch (reasonText) {
      setError(reasonText instanceof Error ? reasonText.message : '导出失败')
    }
  }

  async function saveSegment(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await adminApi('/admin/segments', { method: 'POST', body: JSON.stringify({ name: segmentName, stage, query }) })
      setSegmentOpen(false)
      setSegmentName('')
      setNotice('分群已保存')
      await load()
    } catch (reasonText) {
      setError(reasonText instanceof Error ? reasonText.message : '保存失败')
    }
  }

  async function changeStatus(event: FormEvent) {
    event.preventDefault()
    if (!manage) return
    setError('')
    try {
      const next = manage.status === 'suspended' ? 'active' : 'suspended'
      await adminApi(`/admin/users/${manage.id}/status`, { method: 'POST', body: JSON.stringify({ status: next, reason }) })
      setManage(null)
      setReason('')
      setNotice('用户状态已更新')
      await load()
    } catch (reasonText) {
      setError(reasonText instanceof Error ? reasonText.message : '更新失败')
    }
  }

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="User intelligence" title="用户数据管理" description="当前租户的账号、状态和最近操作。敏感邮箱默认脱敏。" action={<button className={secondaryButton} onClick={() => void exportUsers()}><Download className="size-4" /> 安全导出</button>} />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <div className="metric-grid mb-5">
        <MetricCard label="平台用户" value={String(summary.users)} icon={Users} />
        <MetricCard label="活跃" value={String(summary.active)} icon={UserCheck} tone="green" />
        <MetricCard label="已停用" value={String(summary.suspended)} icon={Clock3} tone="amber" />
        <MetricCard label="已保存分群" value={String(segments.length)} icon={ShieldAlert} tone="violet" />
      </div>
      <FilterBar value={query} onChange={setQuery} placeholder="搜索用户 ID、名称或脱敏邮箱">
        <select className={selectClass} value={stage} onChange={(event) => setStage(event.target.value)} aria-label="生命周期阶段">{['全部阶段', '活跃', '已停用'].map((item) => <option key={item}>{item}</option>)}</select>
        <select className={selectClass} value={plan} onChange={(event) => setPlan(event.target.value)} aria-label="套餐"><option>全部套餐</option>{[...new Set(users.map((user) => user.plan_id).filter(Boolean))].map((item) => <option key={item}>{item}</option>)}</select>
        <button className={secondaryButton} onClick={() => setSegmentOpen(true)}>保存为分群</button>
      </FilterBar>
      {segments.length > 0 && <p className="mb-4 text-sm text-slate-500">已保存分群：{segments.map((item) => `${item.name}（${item.matched}）`).join('、')}</p>}
      <Panel title="用户列表" description={`找到 ${filtered.length} 位用户 · 默认隐藏敏感信息`}>
        {filtered.length === 0 ? <EmptyState query={query || '用户'} /> : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[860px]">
              <thead><tr><th>用户</th><th>套餐</th><th>角色</th><th>状态</th><th>最近更新</th><th>操作</th></tr></thead>
              <tbody>{filtered.map((user) => (
                <tr key={user.id}>
                  <td><div className="font-medium text-slate-900">{user.display_name || user.id}</div><div className="mt-0.5 text-xs text-slate-400">{user.email_masked || '—'} · {user.id}</div></td>
                  <td><StatusBadge>{user.plan_id || '—'}</StatusBadge></td>
                  <td className="text-slate-600">{user.role}</td>
                  <td><StatusBadge tone={user.status === 'suspended' ? 'red' : 'green'}>{user.status === 'suspended' ? '已停用' : '活跃'}</StatusBadge></td>
                  <td className="text-slate-500">{user.updated_at}</td>
                  <td><div className="flex gap-1">
                    <button className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50" onClick={() => adminApi<UserDetail>(`/admin/users/${user.id}`).then(setDetail).catch((reasonText: Error) => setError(reasonText.message))}>查看 360°</button>
                    <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`管理 ${user.display_name || user.id}`} onClick={() => { setManage(user); setReason('') }}><MoreHorizontal className="size-4" /></button>
                  </div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Panel>
      <div className="mt-5 rounded-2xl border border-red-100 bg-red-50/60 p-4 text-sm text-red-700"><Ban className="mr-2 inline size-4" />停用账号必须填写原因，不能停用当前登录账号。</div>
      {detail && (
        <Dialog title="用户 360°" onClose={() => setDetail(null)}>
          <p className="text-lg font-semibold">{detail.display_name}</p>
          <p className="mt-1 text-sm text-slate-500">{detail.email_masked || '无邮箱'} · {detail.username || '无用户名'} · {detail.role}</p>
          <p className="mt-3 text-sm text-slate-600">状态 {detail.status === 'suspended' ? '已停用' : '活跃'} · 套餐 {detail.plan_id || '—'}</p>
          <ul className="mt-4 space-y-2 text-sm text-slate-600">{detail.recent_audit.length === 0 ? <li>暂无相关审计</li> : detail.recent_audit.map((item) => <li key={`${item.action}-${item.created_at}`}>{item.created_at} · {item.action}</li>)}</ul>
        </Dialog>
      )}
      {manage && (
        <Dialog title="管理用户" onClose={() => setManage(null)}>
          <form onSubmit={changeStatus} className="space-y-3">
            <p className="text-sm text-slate-600">将 {manage.display_name || manage.id} {manage.status === 'suspended' ? '恢复为活跃' : '停用'}。</p>
            <input value={reason} onChange={(event) => setReason(event.target.value)} required minLength={2} placeholder="操作原因" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
            <button className={secondaryButton} type="submit">{manage.status === 'suspended' ? '恢复' : '停用'}</button>
          </form>
        </Dialog>
      )}
      {segmentOpen && (
        <Dialog title="保存为分群" onClose={() => setSegmentOpen(false)}>
          <form onSubmit={saveSegment} className="space-y-3">
            <p className="text-sm text-slate-500">使用当前筛选：{stage}{query ? ` · ${query}` : ''}</p>
            <input value={segmentName} onChange={(event) => setSegmentName(event.target.value)} required placeholder="分群名称" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
            <button className={secondaryButton} type="submit">保存</button>
          </form>
        </Dialog>
      )}
    </div>
  )
}
