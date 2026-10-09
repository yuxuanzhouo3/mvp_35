import type { ReactNode } from 'react'
import { Globe2 } from 'lucide-react'
import { GuideVideo } from '@/components/guide-video'

export function AuthShell({ title, copy, children }: { title: string; copy: string; children: ReactNode }) {
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-background px-4 py-12 text-[11px] [&_a]:!text-[11px] [&_button]:!text-[11px] [&_h1]:!text-[13px] [&_input]:!text-[11px] [&_label]:!text-[11px] [&_p]:!text-[11px]">
      <div className="absolute right-4 top-4"><GuideVideo className="!min-h-7 !px-2 !py-1 !text-[11px]" /></div>
      <div className="soft-card w-full max-w-sm p-5">
        <a href="/" className="mb-3 flex items-center gap-1.5 !text-[12px]" aria-label="返回首页">
          <span className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Globe2 className="size-3" />
          </span>
          <span className="font-semibold tracking-tight">Pick<span className="text-primary">Global</span></span>
        </a>
        <h1 className="text-[13px] font-semibold leading-5 tracking-tight">{title}</h1>
        <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{copy}</p>
        <div className="mt-3">{children}</div>
      </div>
    </main>
  )
}

export const authInput = 'mt-1 w-full rounded-md border border-border bg-background px-2 py-1 text-[11px]'
export const authButton = 'mt-3 w-full rounded-md bg-primary px-2 py-1.5 text-[11px] font-medium text-primary-foreground disabled:opacity-50'
