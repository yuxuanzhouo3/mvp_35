'use client'

import { MouseEvent, useEffect, useState } from 'react'

type PlacementAd = {
  id: string
  title: string
  link_url: string
  media_type?: string
}

function websiteHost(link: string) {
  try {
    return new URL(link).host
  } catch {
    return ''
  }
}

export function AdSlot({ placement, className = '' }: { placement: string; className?: string }) {
  const [ad, setAd] = useState<PlacementAd | null>(null)
  const [show, setShow] = useState(true)

  useEffect(() => {
    function sync() {
      setShow(document.documentElement.dataset.ads !== 'off')
    }
    sync()
    window.addEventListener('pickglobal-appearance', sync)
    return () => window.removeEventListener('pickglobal-appearance', sync)
  }, [])

  useEffect(() => {
    let cancelled = false
    fetch(`/api/v1/placements/${placement}`, { cache: 'no-store' })
      .then((response) => response.json())
      .then((body) => {
        if (!cancelled) setAd(body?.data?.ad || null)
      })
      .catch(() => {
        if (!cancelled) setAd(null)
      })
    return () => {
      cancelled = true
    }
  }, [placement])

  if (!show || !ad?.link_url) return null
  const host = websiteHost(ad.link_url)

  function openAd(event: MouseEvent<HTMLAnchorElement>) {
    const href = ad?.link_url || ''
    if (!href) return
    event.preventDefault()
    if (ad?.id) {
      void fetch(`/api/v1/ads/${ad.id}/click`, { method: 'POST', keepalive: true }).catch(() => undefined)
    }
    const opened = window.open(href, '_blank', 'noopener,noreferrer')
    if (!opened) window.location.assign(href)
  }

  return (
    <a
      href={ad.link_url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={openAd}
      className={`group flex min-h-16 w-full items-center justify-between gap-3 rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3.5 text-left transition hover:border-primary/40 hover:bg-primary/10 sm:gap-4 sm:px-5 sm:py-4 ${className}`}
    >
      <span className="min-w-0">
        <span className="text-xs font-semibold uppercase tracking-wide text-primary">广告</span>
        <span className="mt-1 block truncate text-base font-semibold text-foreground">{ad.title}</span>
        {host && <span className="mt-0.5 block truncate text-xs text-muted-foreground">{host}</span>}
      </span>
      <span className="shrink-0 rounded-full bg-primary px-3 py-2 text-sm font-medium text-primary-foreground">打开网站</span>
    </a>
  )
}
