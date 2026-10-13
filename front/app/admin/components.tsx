'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { type ComponentType, type ReactNode, useEffect, useState } from 'react'
import { AdminSession, adminApi, adminToken, clearAdminToken, downloadText } from '@/lib/admin-session'
import { GuideVideo } from '@/components/guide-video'
import {
  BarChart3,
  Bell,
  ChevronDown,
  Download,
  Globe2,
  LayoutDashboard,
  MailCheck,
  Menu,
  Megaphone,
  Search,
  Settings,
  ShieldCheck,
  UserPlus,
  Users,
} from 'lucide-react'

type Icon = ComponentType<{ className?: string }>
type Tone = 'blue' | 'green' | 'emerald' | 'amber' | 'red' | 'violet' | 'slate'

const nav = [
  { href: '/admin', label: '运营总览', icon: LayoutDashboard, kind: 'overview' },
  { href: '/admin/ads', label: '广告管理', icon: Megaphone, kind: 'ads' },
  { href: '/admin/users', label: '用户数据', icon: Users, kind: 'users' },
  { href: '/admin/analytics', label: '行为分析', icon: BarChart3, kind: 'analytics' },
  { href: '/admin/invitations', label: '用户邀请', icon: UserPlus, kind: 'invitations' },
  { href: '/admin/recall', label: '用户召回', icon: MailCheck, kind: 'recall' },
]

const governance = [
  { href: '/admin/audit', label: '审计日志', icon: ShieldCheck, kind: 'audit' },
  { href: '/admin/settings', label: '平台设置', icon: Settings, kind: 'settings' },
]

function NavLinks({ items, close, pathname, onExport }: { items: typeof nav; close?: () => void; pathname: string; onExport: (kind: string, label: string) => void }) {
  return (
    <>
      {items.map(({ href, label, icon: NavIcon, kind }) => {
        const active = href === '/admin' ? pathname === href : pathname.startsWith(href)
        return (
          <div key={href} className={`flex items-center rounded-xl pr-1.5 ${active ? 'bg-blue-500 text-white shadow-md shadow-blue-950/25' : 'text-slate-300 hover:bg-white/8 hover:text-white'}`}>
            <Link href={href} onClick={close} className="admin-focus flex min-w-0 flex-1 items-center gap-3 rounded-xl px-3 py-3 text-sm">
              <NavIcon className="size-[18px] shrink-0" />
              <span className="truncate">{label}</span>
            </Link>
            <button
              type="button"
              aria-label={`导出${label}`}
              className={`admin-focus inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold ${active ? 'bg-white/15 text-white' : 'bg-white/8 text-slate-200 hover:bg-white/15 hover:text-white'}`}
              onClick={() => onExport(kind, label)}
            >
              <Download className="size-3" />
              导出
            </button>
          </div>
        )
      })}
    </>
  )
}

function Sidebar({ close, session, onLogout, onExport }: { close?: () => void; session: AdminSession | null; onLogout: () => void; onExport: (kind: string, label: string) => void }) {
  const pathname = usePathname()
  const [accountOpen, setAccountOpen] = useState(false)
  const name = session?.user.display_name || '平台管理员'
  return (
    <div className="flex h-full flex-col bg-[#10203f] text-white">
      <Link href="/" className="flex h-20 items-center gap-3 border-b border-white/10 px-6" onClick={close}>
        <div className="grid size-10 place-items-center rounded-xl bg-blue-500 shadow-lg shadow-blue-950/30"><Globe2 className="size-5" /></div>
        <div><div className="font-bold tracking-tight">PickGlobal</div><div className="text-[10px] uppercase tracking-[.18em] text-blue-200">Platform Admin</div></div>
      </Link>
      <nav className="admin-scrollbar flex-1 space-y-1 overflow-y-auto p-4" aria-label="管理后台导航">
        <div className="px-3 pb-2 pt-2 text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">Growth operations</div>
        <NavLinks items={nav} close={close} pathname={pathname} onExport={onExport} />
        <div className="px-3 pb-2 pt-6 text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">Governance</div>
        <NavLinks items={governance} close={close} pathname={pathname} onExport={onExport} />
      </nav>
      <div className="relative border-t border-white/10 p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        {accountOpen && (
          <div className="absolute bottom-20 left-4 right-4 rounded-xl border border-white/10 bg-[#1b315c] p-2 shadow-xl">
            <Link href="/admin/settings" onClick={close} className="block rounded-lg px-3 py-2 text-sm text-slate-200 hover:bg-white/10">平台设置</Link>
            <button type="button" onClick={onLogout} className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10">退出登录</button>
          </div>
        )}
        <button type="button" onClick={() => setAccountOpen((open) => !open)} className="admin-focus flex w-full items-center gap-3 rounded-xl bg-white/5 p-3 text-left" aria-expanded={accountOpen} aria-label="账号菜单">
          <div className="grid size-9 place-items-center rounded-full bg-emerald-400/15 text-xs font-bold text-emerald-300">{name.slice(0, 1)}</div>
          <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{name}</div><div className="text-[11px] text-slate-400">{session?.user.username || session?.role || 'admin'}</div></div>
          <ChevronDown className="size-4 text-slate-400" />
        </button>
      </div>
    </div>
  )
}

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [ready, setReady] = useState(false)
  const [session, setSession] = useState<AdminSession | null>(null)
  const [label, setLabel] = useState('TEST')
  const [query, setQuery] = useState('')
  const [notesOpen, setNotesOpen] = useState(false)
  const [notes, setNotes] = useState<Array<{ id: string; action: string; created_at?: string }>>([])
  const [exportNote, setExportNote] = useState('')

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted || pathname === '/admin/login') return
    if (!adminToken()) {
      router.replace('/admin/login')
      return
    }
    adminApi<AdminSession>('/me')
      .then((next) => {
        setSession(next)
        setReady(true)
      })
      .catch(() => router.replace('/admin/login'))
    adminApi<{ environment_label?: string }>('/admin/settings')
      .then((row) => setLabel(row.environment_label || 'TEST'))
      .catch(() => undefined)
  }, [mounted, pathname, router])

  if (!mounted || pathname === '/admin/login') return <>{children}</>

  async function exportNav(kind: string, label: string) {
    setExportNote('')
    try {
      const file = await adminApi<{ filename: string; body: string | object }>(`/admin/exports/${kind}`, { method: 'POST' })
      const text = typeof file.body === 'string' ? file.body : JSON.stringify(file.body, null, 2)
      const type = file.filename.endsWith('.json') ? 'application/json' : 'text/csv;charset=utf-8'
      downloadText(file.filename, text, type)
      setExportNote(`${label}已导出`)
    } catch (reason) {
      setExportNote(reason instanceof Error ? reason.message : '导出失败')
    }
  }

  async function logout() {
    try {
      await adminApi('/auth/logout', { method: 'POST' })
    } catch {
      /* token may already be gone */
    }
    clearAdminToken()
    router.replace('/admin/login')
  }

  async function openNotes() {
    setNotesOpen((current) => !current)
    if (notesOpen) return
    const page = await adminApi<{ items: Array<{ id: string; action: string; created_at?: string }> }>('/admin/audit')
    setNotes(page.items.slice(0, 6))
  }

  if (!ready) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">正在确认登录状态</div>

  return (
    <div className="min-h-screen bg-[#f5f7fb]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block"><Sidebar session={session} onLogout={logout} onExport={(kind, label) => void exportNav(kind, label)} /></aside>
      {open && <div className="fixed inset-0 z-50 lg:hidden"><button aria-label="关闭菜单" className="absolute inset-0 bg-slate-950/50" onClick={() => setOpen(false)} /><aside className="relative h-full w-72 shadow-2xl"><Sidebar close={() => setOpen(false)} session={session} onLogout={logout} onExport={(kind, label) => void exportNav(kind, label)} /></aside></div>}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-20 items-center gap-3 border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <button className="admin-focus rounded-xl border border-slate-200 p-2.5 text-slate-600 lg:hidden" onClick={() => setOpen(true)} aria-label="打开菜单"><Menu className="size-5" /></button>
          <form className="relative hidden max-w-xl flex-1 sm:block" onSubmit={(event) => { event.preventDefault(); router.push(`/admin/search?q=${encodeURIComponent(query.trim())}`) }}>
            <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} className="admin-focus w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-20 text-sm" placeholder="搜索用户、活动、广告、邀请码或页面停留" />
            <button className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white" type="submit">搜索</button>
          </form>
          <div className="relative ml-auto flex items-center gap-2">
            <GuideVideo />
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold tracking-wide text-amber-700">{label}</span>
            <button className="admin-focus relative rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600" aria-label="通知" aria-expanded={notesOpen} onClick={() => void openNotes()}><Bell className="size-5" /><span className="absolute right-2 top-2 size-2 rounded-full bg-red-500 ring-2 ring-white" /></button>
            {notesOpen && (
              <div className="absolute right-0 top-14 z-30 max-h-[min(24rem,calc(100dvh-7.5rem))] w-[min(20rem,calc(100vw-1.5rem))] overflow-y-auto overscroll-contain rounded-2xl border border-slate-200 bg-white p-3 shadow-xl">
                <div className="mb-2 text-sm font-semibold text-slate-900">最近操作</div>
                {notes.length === 0 ? <p className="text-sm text-slate-400">暂无通知</p> : notes.map((item) => (
                  <Link key={item.id} href="/admin/audit" onClick={() => setNotesOpen(false)} className="block rounded-lg px-2 py-2 text-sm hover:bg-slate-50">
                    <div className="font-medium text-slate-800">{item.action}</div>
                    <div className="text-xs text-slate-400">{item.created_at}</div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </header>
        {exportNote && <p className="border-b border-emerald-100 bg-emerald-50 px-4 py-2 text-sm text-emerald-800 sm:px-6 lg:px-8">{exportNote}</p>}
        <main className="p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  )
}

export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4">
      <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" aria-label="关闭">关闭</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Notice({ message, tone = 'green' }: { message: string; tone?: 'green' | 'red' }) {
  if (!message) return null
  const color = tone === 'red' ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-800'
  return <p className={`mb-4 rounded-xl border px-4 py-3 text-sm ${color}`}>{message}</p>
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="mb-2 text-[10px] font-bold uppercase tracking-[.19em] text-blue-600">{eyebrow}</div><h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">{title}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{description}</p></div>{action}</div>
}

export function MetricCard({ label, value, change, icon: MetricIcon, tone = 'blue', note, highlight = false, onClick }: { label: string; value: string; change?: string; icon: Icon; tone?: Tone; note?: string; highlight?: boolean; onClick?: () => void }) {
  const colors: Record<Tone, string> = { blue: 'bg-blue-50 text-blue-600', green: 'bg-emerald-50 text-emerald-600', emerald: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600', red: 'bg-red-50 text-red-600', violet: 'bg-violet-50 text-violet-600', slate: 'bg-slate-100 text-slate-600' }
  const className = `rounded-2xl border bg-white p-5 text-left shadow-sm ${highlight ? 'border-blue-400 ring-2 ring-blue-100' : 'border-slate-200'} ${onClick ? 'w-full' : ''}`
  const body = <><div className="flex items-start justify-between"><div className={`grid size-10 place-items-center rounded-xl ${colors[tone]}`}><MetricIcon className="size-5" /></div>{change && <span className={`text-xs font-semibold ${change.startsWith('-') ? 'text-red-600' : 'text-emerald-600'}`}>{change}</span>}</div><div className="mt-5 text-2xl font-bold tracking-tight text-slate-950">{value}</div><div className="mt-1 text-sm text-slate-500">{label}</div>{note && <div className="mt-2 text-xs text-slate-400">{note}</div>}</>
  if (onClick) return <button type="button" className={className} onClick={onClick}>{body}</button>
  return <div className={className}>{body}</div>
}

export function Panel({ title, description, action, children, className = '' }: { title: string; description?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}><div className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4"><div><h2 className="font-semibold text-slate-900">{title}</h2>{description && <p className="mt-1 text-xs text-slate-400">{description}</p>}</div>{action}</div>{children}</section>
}

export function StatusBadge({ children, tone = 'slate' }: { children: ReactNode; tone?: Tone }) {
  const colors: Record<Tone, string> = { blue: 'bg-blue-50 text-blue-700 ring-blue-600/15', green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15', emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15', amber: 'bg-amber-50 text-amber-700 ring-amber-600/15', red: 'bg-red-50 text-red-700 ring-red-600/15', violet: 'bg-violet-50 text-violet-700 ring-violet-600/15', slate: 'bg-slate-100 text-slate-600 ring-slate-500/15' }
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${colors[tone]}`}>{children}</span>
}

export function FilterBar({ search, onSearch, value, onChange, placeholder, children }: { search?: string; onSearch?: (value: string) => void; value?: string; onChange?: (value: string) => void; placeholder: string; children?: ReactNode }) {
  const current = value ?? search ?? ''
  const update = onChange ?? onSearch
  return <div className="mb-5 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm"><div className="relative min-w-[15rem] flex-1"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><input value={current} onChange={(event) => update?.(event.target.value)} className="admin-focus w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm" placeholder={placeholder} /></div>{children}</div>
}

export function Select({ value, onChange, label, children }: { value: string; onChange: (value: string) => void; label: string; children: ReactNode }) {
  return <select className={selectClass} value={value} onChange={(event) => onChange(event.target.value)} aria-label={label}>{children}</select>
}

export function EmptyState({ query }: { query: string }) {
  return <div className="grid place-items-center px-5 py-16 text-center"><div className="grid size-12 place-items-center rounded-2xl bg-slate-100"><Search className="size-5 text-slate-400" /></div><div className="mt-3 font-medium text-slate-700">没有匹配结果</div><div className="mt-1 text-sm text-slate-400">尝试调整搜索词“{query}”或筛选条件</div></div>
}

export const primaryButton = 'admin-focus inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700'
export const secondaryButton = 'admin-focus inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50'
export const selectClass = 'admin-focus rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700'
export const chartTooltipStyle = { borderRadius: 12, borderColor: '#e2e8f0', boxShadow: '0 8px 24px rgba(15, 23, 42, .08)' }
