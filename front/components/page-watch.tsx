'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

const GAP_MS = 2500
const MIN_DWELL_MS = 1000

function pageKey(pathname: string) {
  const parts = pathname.split('/').filter(Boolean).map((part) => part.toLowerCase())
  if (parts.length === 0) return 'home'
  if (parts[0] === 'workspace' && parts[1] === 'reports') return 'report-detail'
  if (parts[0] === 'workspace' && parts[1] === 'acquire' && parts[2]) {
    const channel = parts[2].replace(/[^a-z0-9_-]/g, '').slice(0, 24)
    return channel ? `acquire-${channel}` : 'workspace-acquire'
  }
  const key = parts.join('-').replace(/[^a-z0-9_-]/g, '').slice(0, 40)
  return key || 'home'
}

function sectionOf(node: EventTarget | null) {
  if (!(node instanceof Element)) return null
  const marked = node.closest('[data-watch], section[id]')
  if (!marked) return null
  const id = marked.getAttribute('data-watch') || marked.id
  return id && /^[a-z0-9][a-z0-9_-]{0,39}$/.test(id) ? id : null
}

function send(path: string, section: string, kind: 'dwell' | 'click' | 'leave', durationMs: number, clicks = 0) {
  const body = JSON.stringify({
    path,
    section,
    kind,
    duration_ms: Math.max(0, Math.round(durationMs)),
    clicks,
  })
  const blob = new Blob([body], { type: 'application/json' })
  if (navigator.sendBeacon?.('/api/v1/behavior', blob)) return
  void fetch('/api/v1/behavior', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => undefined)
}

export function PageWatch() {
  const pathname = usePathname()

  useEffect(() => {
    if (!pathname) return
    const page = pageKey(pathname)
    const pageStart = performance.now()
    let pageOpen = true
    const finishPage = (kind: 'dwell' | 'leave') => {
      if (!pageOpen) return
      pageOpen = false
      const duration = performance.now() - pageStart
      if (kind === 'dwell' && duration < MIN_DWELL_MS) return
      send(pathname, page, kind, duration)
    }

    const visible = new Map<string, number>()
    const observer = new IntersectionObserver(
      (entries) => {
        const now = performance.now()
        for (const entry of entries) {
          const id = sectionOf(entry.target)
          if (!id || id === page) continue
          const showing = entry.isIntersecting && entry.intersectionRatio >= 0.35
          if (showing) {
            if (!visible.has(id)) visible.set(id, now)
            continue
          }
          const start = visible.get(id)
          if (start == null) continue
          visible.delete(id)
          const duration = now - start
          if (duration >= MIN_DWELL_MS) send(pathname, id, 'dwell', duration)
        }
      },
      { threshold: [0.35] },
    )
    document.querySelectorAll('section[id], [data-watch]').forEach((node) => observer.observe(node))

    let burst: { section: string; start: number; last: number; clicks: number; timer: number } | null = null
    const flush = () => {
      if (!burst) return
      const current = burst
      burst = null
      if (current.clicks >= 2) send(pathname, current.section, 'click', current.last - current.start, current.clicks)
    }
    const onClick = (event: MouseEvent) => {
      const section = sectionOf(event.target) || page
      const now = performance.now()
      if (burst && burst.section === section && now - burst.last < GAP_MS) {
        burst.clicks += 1
        burst.last = now
        window.clearTimeout(burst.timer)
        burst.timer = window.setTimeout(flush, GAP_MS)
        return
      }
      flush()
      burst = { section, start: now, last: now, clicks: 1, timer: window.setTimeout(flush, GAP_MS) }
    }
    const onHide = () => {
      if (document.visibilityState === 'visible') return
      flush()
      const now = performance.now()
      for (const [id, start] of visible) {
        send(pathname, id, 'leave', now - start)
        visible.delete(id)
      }
      finishPage('leave')
    }

    document.addEventListener('click', onClick, true)
    document.addEventListener('visibilitychange', onHide)
    window.addEventListener('pagehide', onHide)
    return () => {
      flush()
      const now = performance.now()
      for (const [id, start] of visible) {
        const duration = now - start
        if (duration >= MIN_DWELL_MS) send(pathname, id, 'dwell', duration)
      }
      finishPage('dwell')
      observer.disconnect()
      document.removeEventListener('click', onClick, true)
      document.removeEventListener('visibilitychange', onHide)
      window.removeEventListener('pagehide', onHide)
    }
  }, [pathname])

  return null
}
