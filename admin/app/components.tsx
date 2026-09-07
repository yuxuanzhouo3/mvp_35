'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { type ComponentType, type ReactNode, useState } from 'react'
import {
  Activity,
  BarChart3,
  Bell,
  ChevronDown,
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
  X,
} from 'lucide-react'

type Icon = ComponentType<{ className?: string }>
type Tone = 'blue' | 'green' | 'amber' | 'red' | 'violet' | 'slate'

const nav = [
  { href: '/', label: '运营总览', icon: LayoutDashboard },
  { href: '/ads', label: '广告管理', icon: Megaphone },
  { href: '/users', label: '用户数据', icon: Users },
  { href: '/analytics', label: '行为分析', icon: BarChart3 },
  { href: '/invitations', label: '用户邀请', icon: UserPlus },
  { href: '/recall', label: '用户召回', icon: MailCheck },
]

function Sidebar({ close }: { close?: () => void }) {
  const pathname = usePathname()
  return (
    <div className="flex h-full flex-col bg-[#10203f] text-white">
      <div className="flex h-20 items-center gap-3 border-b border-white/10 px-6">
        <div className="grid size-10 place-items-center rounded-xl bg-blue-500 shadow-lg shadow-blue-950/30">
          <Globe2 className="size-5" />
        </div>
        <div>
          <div className="font-bold tracking-tight">PickGlobal</div>
          <div className="text-[10px] uppercase tracking-[.18em] text-blue-200">Platform Admin</div>
        </div>
      </div>
      <nav className="admin-scrollbar flex-1 space-y-1 overflow-y-auto p-4" aria-label="管理后台导航">
        <div className="px-3 pb-2 pt-2 text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">
          Growth operations
        </div>
        {nav.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              onClick={close}
              className={`focus-ring flex items-center gap-3 rounded-xl px-3 py-3 text-sm transition ${
                active ? 'bg-blue-500 text-white shadow-md shadow-blue-950/25' : 'text-slate-300 hover:bg-white/8 hover:text-white'
              }`}
            >
              <Icon className="size-[18px]" />
              {label}
            </Link>
          )
        })}
        <div className="px-3 pb-2 pt-6 text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">
          Governance
        </div>
        <a className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400" href="#audit">
          <ShieldCheck className="size-[18px]" /> 审计日志
        </a>
        <a className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400" href="#settings">
          <Settings className="size-[18px]" /> 平台设置
        </a>
      </nav>
      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-xl bg-white/5 p-3">
          <div className="grid size-9 place-items-center rounded-full bg-emerald-400/15 text-xs font-bold text-emerald-300">YZ</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">平台管理员</div>
            <div className="text-[11px] text-slate-400">Super Admin</div>
          </div>
          <ChevronDown className="size-4 text-slate-400" />
        </div>
      </div>
    </div>
  )
}

export function AdminShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block"><Sidebar /></aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button aria-label="关闭菜单" className="absolute inset-0 bg-slate-950/50" onClick={() => setOpen(false)} />
          <aside className="relative h-full w-72 shadow-2xl"><Sidebar close={() => setOpen(false)} /></aside>
        </div>
      )}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-20 items-center gap-3 border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <button className="focus-ring rounded-xl border border-slate-200 p-2.5 text-slate-600 lg:hidden" onClick={() => setOpen(true)} aria-label="打开菜单">
            <Menu className="size-5" />
          </button>
          <div className="relative hidden max-w-xl flex-1 sm:block">
            <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <input className="focus-ring w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-sm" placeholder="搜索用户、活动、广告或邀请码" />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold tracking-wide text-amber-700">TEST</span>
            <button className="focus-ring relative rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600" aria-label="通知">
              <Bell className="size-5" /><span className="absolute right-2 top-2 size-2 rounded-full bg-red-500 ring-2 ring-white" />
            </button>
          </div>
        </header>
        <main className="p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  )
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <div className="mb-2 text-[10px] font-bold uppercase tracking-[.19em] text-blue-600">{eyebrow}</div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{description}</p>
      </div>
      {action}
    </div>
  )
}

export function MetricCard({ label, value, change, icon: Icon, tone = 'blue', note }: { label: string; value: string; change?: string; icon: Icon; tone?: Tone; note?: string }) {
  const colors: Record<Tone, string> = {
    blue: 'bg-blue-50 text-blue-600', green: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600', violet: 'bg-violet-50 text-violet-600', slate: 'bg-slate-100 text-slate-600',
  }
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div className={`grid size-10 place-items-center rounded-xl ${colors[tone]}`}><Icon className="size-5" /></div>
        {change && <span className={`text-xs font-semibold ${change.startsWith('-') ? 'text-red-600' : 'text-emerald-600'}`}>{change}</span>}
      </div>
      <div className="mt-5 text-2xl font-bold tracking-tight text-slate-950">{value}</div>
      <div className="mt-1 text-sm text-slate-500">{label}</div>
      {note && <div className="mt-2 text-xs text-slate-400">{note}</div>}
    </div>
  )
}

export function Panel({ title, description, action, children, className = '' }: { title: string; description?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}>
      <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div><h2 className="font-semibold text-slate-900">{title}</h2>{description && <p className="mt-1 text-xs text-slate-400">{description}</p>}</div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function StatusBadge({ children, tone = 'slate' }: { children: ReactNode; tone?: Tone }) {
  const colors: Record<Tone, string> = {
    blue: 'bg-blue-50 text-blue-700 ring-blue-600/15', green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
    amber: 'bg-amber-50 text-amber-700 ring-amber-600/15', red: 'bg-red-50 text-red-700 ring-red-600/15',
    violet: 'bg-violet-50 text-violet-700 ring-violet-600/15', slate: 'bg-slate-100 text-slate-600 ring-slate-500/15',
  }
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${colors[tone]}`}>{children}</span>
}

export function FilterBar({ value, onChange, placeholder, children }: { value: string; onChange: (value: string) => void; placeholder: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="relative min-w-[15rem] flex-1">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
        <input value={value} onChange={(event) => onChange(event.target.value)} className="focus-ring w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm" placeholder={placeholder} />
      </div>
      {children}
    </div>
  )
}

export function EmptyState({ query }: { query: string }) {
  return (
    <div className="grid place-items-center px-5 py-16 text-center">
      <div className="grid size-12 place-items-center rounded-2xl bg-slate-100"><Search className="size-5 text-slate-400" /></div>
      <div className="mt-3 font-medium text-slate-700">没有匹配结果</div>
      <div className="mt-1 text-sm text-slate-400">尝试调整搜索词“{query}”或筛选条件</div>
    </div>
  )
}

export const primaryButton = 'focus-ring inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700'
export const secondaryButton = 'focus-ring inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50'
export const selectClass = 'focus-ring rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700'

export const chartTooltipStyle = { borderRadius: 12, borderColor: '#e2e8f0', boxShadow: '0 8px 24px rgba(15, 23, 42, .08)' }
export const overviewIcon = Activity
export const closeIcon = X
