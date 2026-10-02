import type { ReactNode } from 'react'
import { Globe2 } from 'lucide-react'
import { GuideVideo } from '@/components/guide-video'

export function AuthShell({ title, copy, children }: { title: string; copy: string; children: ReactNode }) {
  return (
    <main className="relative grid min-h-screen place-items-center bg-background px-4 py-10">
      <div className="absolute right-4 top-4"><GuideVideo /></div>
      <div className="relative top-10 w-full max-w-md rounded-3xl border border-border bg-card p-8 shadow-sm">
        <a href="/" className="mb-6 flex items-center gap-2" aria-label="返回首页">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Globe2 className="size-4" />
          </span>
          <span className="font-semibold tracking-tight">Pick<span className="text-primary">Global</span></span>
        </a>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{copy}</p>
        <div className="mt-6">{children}</div>
      </div>
    </main>
  )
}

export const authInput = 'mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm'
export const authButton = 'mt-6 w-full rounded-xl bg-primary px-3 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50'
