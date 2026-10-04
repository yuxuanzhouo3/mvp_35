'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Globe2, MessageSquare } from 'lucide-react'
import { GuideVideo } from '@/components/guide-video'
import { UserMenu } from '@/components/user-menu'
import { AdSlot } from '@/components/ad-slot'
import { ChatSidebar } from '@/components/chat-sidebar'
import { api } from '@/lib/api'
import { accessToken, logoutSession } from '@/lib/session'

const links = [
  ['/workspace', '看板'],
  ['/workspace/products', '选品分析'],
  ['/workspace/acquire', '获客经营'],
  ['/workspace/billing', '账单'],
]

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const [name, setName] = useState('')
  const [ready, setReady] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    if (!accessToken()) {
      setReady(false)
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
      return
    }
    setReady(true)
  }, [pathname, router])

  useEffect(() => {
    if (!accessToken()) return
    let cancelled = false
    api<{ user: { display_name?: string; username?: string; email?: string; phone?: string } }>('/users/me')
      .then((me) => {
        if (cancelled) return
        const user = me.user
        setName(user.display_name || user.username || user.email || user.phone || '')
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (window.matchMedia('(min-width: 768px)').matches) setChatOpen(true)
  }, [])

  return (
    <div className="min-h-screen bg-background pb-28 md:pb-0">
      <header className="site-header sticky top-0 z-40 border-b border-border/70 bg-background/90 backdrop-blur-md">
        <div className="container flex h-14 items-center justify-between gap-4 md:h-16">
          <Link href="/" className="flex items-center gap-2" aria-label="返回 PickGlobal 首页">
            <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Globe2 className="size-[18px]" />
            </span>
            <span className="font-semibold tracking-tight">Pick<span className="text-primary">Global</span></span>
          </Link>
          <nav className="hidden items-center gap-1 rounded-2xl border border-border bg-card p-1 text-sm shadow-sm md:flex">
            {links.map(([href, label]) => {
              const active = href === '/workspace' ? pathname === href : pathname.startsWith(href)
              return (
                <Link key={href} href={href} className={`rounded-xl px-3 py-1.5 ${active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}>
                  {label}
                </Link>
              )
            })}
          </nav>
          <div className="flex min-w-0 items-center gap-2 text-xs sm:gap-3 sm:text-sm">
            <button type="button" className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 ${chatOpen ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`} aria-expanded={chatOpen} onClick={() => setChatOpen((open) => !open)}>
              <MessageSquare className="size-4" />
              对话
            </button>
            <UserMenu name={name || '账号'} onLogout={() => void logoutSession().then(() => router.replace('/login'))} />
            <GuideVideo className="shrink-0" />
          </div>
        </div>
      </header>
      <div className={chatOpen ? 'md:mr-80' : ''}>
      <div className="container py-6 md:py-8" data-watch={pathname.startsWith('/workspace/products') ? 'report' : pathname.startsWith('/workspace/acquire') ? 'acquire' : pathname.startsWith('/workspace/billing') ? 'billing' : 'workspace'}>
        {ready ? (
          <>
            <AdSlot placement="dashboard_top" className="mb-5 max-md:mb-4" />
            {children}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">正在确认登录</p>
        )}
      </div>
      </div>
      {ready && <ChatSidebar open={chatOpen} onClose={() => setChatOpen(false)} />}
      <nav className="phone-dock md:hidden" aria-label="手机导航">
        {links.map(([href, label]) => {
          const active = href === '/workspace' ? pathname === href : pathname.startsWith(href)
          return (
            <Link key={href} href={href} className={`flex min-h-12 flex-1 items-center justify-center rounded-xl text-sm font-medium ${active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}>
              {label}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
