'use client'

import { useEffect } from 'react'

export function ReportDialog({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[min(42rem,calc(100vh-2rem))] w-full max-w-xl overflow-y-auto rounded-2xl border border-border bg-card p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          <button type="button" className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-sm" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  )
}
