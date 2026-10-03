'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Globe2 } from 'lucide-react'
import { GuideVideo } from '@/components/guide-video'
import { AdSlot } from '@/components/ad-slot'
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
          <nav className="hidden items-center gap-1 text-sm md:flex">
            {links.map(([href, label]) => {
              const active = href === '/workspace' ? pathname === href : pathname.startsWith(href)
              return (
                <Link key={href} href={href} className={`rounded-lg px-3 py-1.5 ${active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
                  {label}
                </Link>
              )
            })}
          </nav>
          <div className="flex min-w-0 items-center gap-2 text-xs sm:gap-3 sm:text-sm">
            <button type="button" className="shrink-0 text-muted-foreground hover:text-foreground" onClick={() => void logoutSession().then(() => router.replace('/login'))}>退出</button>
            {name && <span className="min-w-0 max-w-[6.5rem] truncate text-muted-foreground sm:max-w-32">{name}</span>}
            <GuideVideo className="mr-3 shrink-0 sm:mr-0" />
          </div>
        </div>
      </header>
      <div className="container py-6 md:py-8">
        {ready ? (
          <>
            <AdSlot placement="dashboard_top" className="mb-5 max-md:mb-4" />
            {children}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">正在确认登录</p>
        )}
      </div>
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
