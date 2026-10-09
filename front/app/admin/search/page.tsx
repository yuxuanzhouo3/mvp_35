'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { EmptyState, Notice, PageHeader, Panel } from '../components'

type Hit = { id: string; label: string; href: string }
type PageHit = Hit & { path?: string; dwell_ms: number; avg_dwell_ms: number; clicks: number; click_ms: number; leaves: number; leave_ms: number }
type Result = { users: Hit[]; ads: Hit[]; invitations: Hit[]; recalls: Hit[]; pages?: PageHit[] }

function stay(ms: number) {
  if (!ms) return '0 秒'
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${Math.max(seconds, 1)} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分`
}

function SearchResults() {
  const params = useSearchParams()
  const q = params.get('q') || ''
  const [result, setResult] = useState<Result>({ users: [], ads: [], invitations: [], recalls: [], pages: [] })
  const [error, setError] = useState('')

  useEffect(() => {
    if (!q.trim()) return
    adminApi<Result>(`/admin/search?q=${encodeURIComponent(q)}`).then(setResult).catch((reason: Error) => setError(reason.message))
  }, [q])

  const groups = [
    ['用户', result.users],
    ['广告', result.ads],
    ['邀请', result.invitations],
    ['召回', result.recalls],
  ] as const
  const pages = result.pages ?? []
  const total = groups.reduce((sum, [, items]) => sum + items.length, 0) + pages.length

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader eyebrow="Search" title="搜索结果" description={q ? `关键词“${q}”` : '请输入关键词'} />
      <Notice message={error} tone="red" />
      {pages.length > 0 && (
        <Panel title="页面停留" description="主页面和子页面的停留、连续点击、关闭" className="mb-4">
          <ul className="divide-y divide-slate-100">{pages.map((item) => (
            <li key={item.id}>
              <Link href={item.href} className="block px-5 py-3 text-sm hover:bg-slate-50">
                <span className="font-medium text-slate-900">{item.label}</span>
                <span className="mt-1 block text-xs text-slate-500">{item.path} · 停留 {stay(item.dwell_ms)} · 平均 {stay(item.avg_dwell_ms)} · 连续点击 {item.clicks} 下 · 点击 {stay(item.click_ms)} · 关闭 {item.leaves} 次 · 关闭前 {stay(item.leave_ms)}</span>
              </Link>
            </li>
          ))}</ul>
        </Panel>
      )}
      {total === 0 ? <Panel title="没有结果"><EmptyState query={q || '关键词'} /></Panel> : groups.map(([title, items]) => items.length > 0 && (
        <Panel key={title} title={title} className="mb-4">
          <ul className="divide-y divide-slate-100">{items.map((item) => <li key={item.id}><Link href={item.href} className="flex items-center justify-between px-5 py-3 text-sm hover:bg-slate-50"><span className="font-medium text-slate-900">{item.label}</span><span className="font-mono text-xs text-slate-400">{item.id}</span></Link></li>)}</ul>
        </Panel>
      ))}
    </div>
  )
}

export default function SearchPage() {
  return <Suspense fallback={<p className="text-sm text-slate-500">正在搜索</p>}><SearchResults /></Suspense>
}
