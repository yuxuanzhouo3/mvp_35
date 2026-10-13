'use client'

import { useEffect } from 'react'

export function SmsQuotaDialog({ count, cap, onClose }: { count: number; cap: number; onClose: () => void }) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/40 p-4" role="dialog" aria-modal="true" aria-label="短信额度">
      <div className="w-full max-w-sm rounded-2xl bg-card p-5 shadow-xl">
        <h2 className="!text-base font-semibold">短信额度</h2>
        <p className="mt-2 !text-sm !leading-6 text-muted-foreground">
          这个号码今天已发出 {count} 条短信，已到每天 {cap} 条的上限。明天 0 点后才能再收。密码登录不受这条限制。
        </p>
        <button type="button" className="mt-4 h-10 w-full rounded-xl bg-primary !text-sm font-medium text-primary-foreground" onClick={onClose}>
          知道了
        </button>
      </div>
    </div>
  )
}
