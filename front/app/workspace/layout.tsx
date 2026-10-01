'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Globe2 } from 'lucide-react'

const links = [
  ['/workspace', '看板'],
  ['/workspace/products', '选品分析'],
  ['/workspace/acquire', '获客经营'],
]

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
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
        </div>
      </header>
      <div className="container py-6 md:py-8">{children}</div>
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
