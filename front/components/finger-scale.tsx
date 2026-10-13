'use client'

import { useEffect, useRef, useState } from 'react'
import { fingerScaleMode, readClient } from '@/lib/client-adapter'

const MIN = 1
const MAX = 4

function pinchSpan(touches: TouchList) {
  const first = touches[0]
  const second = touches[1]
  return Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY)
}

export function FingerScale() {
  const [watch, setWatch] = useState(false)
  const [level, setLevel] = useState(1)
  const applyRef = useRef<(value: number) => void>(() => {})

  useEffect(() => {
    const decision = fingerScaleMode(readClient(), {
      userAgent: navigator.userAgent,
      shortSide: Math.min(window.screen.width, window.screen.height),
      touchPoints: navigator.maxTouchPoints,
    })
    if (decision.mode === 'off') return

    const root = document.documentElement
    root.dataset.fingerScale = decision.watch ? 'watch' : decision.mode
    setWatch(decision.watch)
    if (decision.mode !== 'gesture') return

    let startDist = 0
    let startZoom = 1
    let zoom = 1

    const apply = (value: number) => {
      zoom = Math.min(MAX, Math.max(MIN, Math.round(value * 100) / 100))
      if (zoom === 1) root.style.removeProperty('zoom')
      else root.style.setProperty('zoom', String(zoom))
      setLevel(zoom)
    }
    applyRef.current = apply

    const onStart = (event: TouchEvent) => {
      if (event.touches.length === 2) {
        startDist = pinchSpan(event.touches)
        startZoom = zoom
      }
    }
    const onMove = (event: TouchEvent) => {
      if (event.touches.length !== 2 || startDist <= 0) return
      event.preventDefault()
      apply(startZoom * (pinchSpan(event.touches) / startDist))
    }
    const onEnd = (event: TouchEvent) => {
      if (event.touches.length < 2) startDist = 0
    }

    document.addEventListener('touchstart', onStart, { passive: true })
    document.addEventListener('touchmove', onMove, { passive: false })
    document.addEventListener('touchend', onEnd)
    document.addEventListener('touchcancel', onEnd)

    return () => {
      document.removeEventListener('touchstart', onStart)
      document.removeEventListener('touchmove', onMove)
      document.removeEventListener('touchend', onEnd)
      document.removeEventListener('touchcancel', onEnd)
      root.style.removeProperty('zoom')
      delete root.dataset.fingerScale
      applyRef.current = () => {}
    }
  }, [])

  if (!watch) return null

  return (
    <div className="watch-zoom" role="group" aria-label="页面缩放">
      <button type="button" onClick={() => applyRef.current(level - 0.25)} aria-label="缩小">−</button>
      <button type="button" onClick={() => applyRef.current(1)} aria-label="恢复原始大小">{Math.round(level * 100)}%</button>
      <button type="button" onClick={() => applyRef.current(level + 0.25)} aria-label="放大">+</button>
    </div>
  )
}
