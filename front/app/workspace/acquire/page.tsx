'use client'

import { Suspense, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChannelMark } from '@/components/brand-marks'
import { RouteBar } from '@/components/route-bar'
import { tintForChannel } from '@/lib/brand-tints'
import { channels } from './channels'

export default function AcquirePage() {
  return <Suspense fallback={<p className="text-sm text-muted-foreground">加载获客工作台…</p>}><AcquireHome /></Suspense>
}

function AcquireHome() {
  const params = useSearchParams()
  const router = useRouter()
  const channel = params.get('channel')
  const seed = params.get('seed_analysis_id')

  useEffect(() => {
    if (!channel || !channels.some((item) => item.id === channel)) return
    const query = seed ? `?seed_analysis_id=${encodeURIComponent(seed)}` : ''
    router.replace(`/workspace/acquire/${channel}${query}`)
  }, [channel, seed, router])

  return (
    <div className="flex flex-col gap-2 pb-[calc(6.5rem+env(safe-area-inset-bottom))] text-[12px] leading-4 md:h-[calc(100dvh-7.25rem)] md:gap-3 md:overflow-hidden md:pb-0 md:text-sm md:leading-5">
      <RouteBar />
      <div className="shrink-0 md:flex md:items-end md:justify-between md:gap-6">
        <div className="min-w-0">
          <span className="eyebrow">路径 B · 九路获客</span>
          <h1 className="mt-1 text-base font-semibold tracking-tight md:mt-1.5 md:text-2xl lg:text-[1.75rem]">线索、触达、成交与召回</h1>
          <p className="mt-1 max-w-3xl text-[11px] leading-4 text-muted-foreground md:mt-1.5 md:text-sm md:leading-5">点开一路。九路进同一线索池。</p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-1.5 sm:gap-3 md:min-h-0 md:flex-1 md:grid-cols-3 md:grid-rows-3 md:gap-3">
        {channels.map((item) => {
          const tint = tintForChannel(item.id)
          return (
            <Link
              key={item.id}
              href={`/workspace/acquire/${item.id}`}
              className={`flex flex-col items-center justify-center rounded-2xl border px-1.5 py-2 text-center transition hover:-translate-y-0.5 md:min-h-0 md:items-start md:justify-start md:rounded-2xl md:px-4 md:py-3.5 md:text-left ${tint.card}`}
            >
              <div className="flex flex-col items-center md:w-full md:flex-row md:items-center md:gap-2.5">
                <ChannelMark id={item.id} className={`mb-1 size-7 md:mb-0 md:size-9 ${tint.code}`} />
                <span className={`text-[10px] font-semibold md:text-xs ${tint.code}`}>{item.code}</span>
              </div>
              <span className="mt-0.5 text-[11px] font-semibold leading-tight md:mt-2.5 md:text-base lg:text-lg">{item.name}</span>
              <span className="mt-0.5 hidden line-clamp-2 text-xs leading-5 text-muted-foreground md:mt-1.5 md:block md:text-[13px] md:leading-5">{item.copy}</span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
