'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { EmptyState, Notice, PageHeader, Panel } from '../components'

type Hit = { id: string; label: string; href: string }
type Result = { users: Hit[]; ads: Hit[]; invitations: Hit[]; recalls: Hit[] }

function SearchResults() {
  const params = useSearchParams()
  const q = params.get('q') || ''
  const [result, setResult] = useState<Result>({ users: [], ads: [], invitations: [], recalls: [] })
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
  const total = groups.reduce((sum, [, items]) => sum + items.length, 0)

  return (
    <div className="mx-auto max-w-[900px]">
      <PageHeader eyebrow="Search" title="搜索结果" description={q ? `关键词“${q}”` : '请输入关键词'} />
      <Notice message={error} tone="red" />
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
