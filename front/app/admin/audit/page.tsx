'use client'

import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { EmptyState, Notice, PageHeader, Panel, secondaryButton } from '../components'

type AuditRow = { id: string; action: string; resource?: string; user_id?: string; created_at?: string }

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([])
  const [error, setError] = useState('')

  function load() {
    adminApi<{ items: AuditRow[] }>('/admin/audit').then((page) => setRows(page.items)).catch((reason: Error) => setError(reason.message))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader eyebrow="Governance" title="审计日志" description="登录、导出、广告、邀请、召回和设置变更都会记在这里。" action={<button className={secondaryButton} onClick={load}>刷新</button>} />
      <Notice message={error} tone="red" />
      <Panel title="最近操作" description={`${rows.length} 条`}>
        {rows.length === 0 ? <EmptyState query="审计" /> : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[720px]">
              <thead><tr><th>时间</th><th>动作</th><th>资源</th><th>操作人</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="text-slate-500">{row.created_at}</td>
                    <td className="font-medium text-slate-900">{row.action}</td>
                    <td className="font-mono text-xs text-slate-500">{row.resource}</td>
                    <td className="font-mono text-xs text-slate-500">{row.user_id}</td>
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
