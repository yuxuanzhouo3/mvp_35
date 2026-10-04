'use client'

import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Play, X } from 'lucide-react'

const SRC = '/guides/yunjian.mp4'

export function GuideVideo({ className = '', onDark = false }: { className?: string; onDark?: boolean }) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const titleId = useId()

  useEffect(() => {
    setMounted(true)
  }, [])

  function close() {
    videoRef.current?.pause()
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    const frame = requestAnimationFrame(() => {
      videoRef.current?.play().catch(() => undefined)
    })
    return () => {
      window.removeEventListener('keydown', onKey)
      cancelAnimationFrame(frame)
    }
  }, [open])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`inline-flex min-h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 text-sm font-medium ${onDark ? 'bg-white/10 text-white hover:bg-white/20' : 'text-foreground hover:bg-muted'} ${className}`}
      >
        <Play className="size-3.5" />
        操作演示
      </button>
      {mounted && open && createPortal(
        <div className="fixed inset-0 z-[200] grid place-items-center bg-slate-950/70 p-4 sm:p-8">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="grid w-full max-w-3xl place-items-center"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="w-full overflow-hidden rounded-2xl bg-black shadow-2xl">
              <div className="flex items-center justify-between gap-3 bg-slate-950 px-4 py-3 text-white">
                <p id={titleId} className="text-sm font-medium">使用教程 · 云健</p>
                <button
                  type="button"
                  onClick={close}
                  className="flex size-9 items-center justify-center rounded-full bg-white text-slate-950"
                  aria-label="关闭演示"
                >
                  <X className="size-5" />
                </button>
              </div>
              <video ref={videoRef} src={SRC} controls playsInline className="max-h-[70vh] w-full bg-black object-contain" />
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
