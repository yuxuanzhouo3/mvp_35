'use client'

import { useState } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { LEGAL_VERSION, docIds, legalDocs, type DocId } from '@/lib/legal-docs'

export { LEGAL_VERSION }

const order: DocId[] = [...docIds]

export function LegalBody({ id }: { id: DocId }) {
  const doc = legalDocs[id]
  return (
    <div className="space-y-4 text-sm leading-6 text-slate-700">
      <p className="font-semibold text-slate-950">{doc.mark}</p>
      <p>生效日期：2026年10月04日</p>
      <p>{doc.principle}</p>
      <div>
        <p className="font-semibold text-slate-950">中文（摘要）</p>
        <ul className="mt-1 list-disc space-y-1 pl-5">{doc.zh.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
      <div>
        <p className="font-semibold text-slate-950">English (Summary)</p>
        <ul className="mt-1 list-disc space-y-1 pl-5">{doc.en.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
      <div className="space-y-3">
        <p className="font-semibold text-slate-950">简要说明</p>
        {doc.details.map((section) => (
          <section key={section.heading}>
            <p className="font-semibold text-slate-950">{section.heading}</p>
            <p className="mt-1">{section.body}</p>
          </section>
        ))}
      </div>
    </div>
  )
}

export function LegalConsent({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  const [open, setOpen] = useState<DocId | null>(null)
  const doc = open ? legalDocs[open] : null
  return (
    <div className="mt-3">
      <div className="flex items-start gap-2">
        <input id="legal-accept" type="checkbox" className="mt-0.5 size-4 shrink-0 rounded border-slate-300" checked={checked} onChange={(event) => onChange(event.target.checked)} />
        <p className="text-left text-xs leading-5 text-slate-500">
          <label htmlFor="legal-accept">我已阅读并同意</label>
          {order.map((id, index) => (
            <span key={id}>{index === 0 ? '' : '和'}<button type="button" className="underline underline-offset-4 hover:text-blue-600" onClick={() => setOpen(id)}>《{legalDocs[id].title}》</button></span>
          ))}
        </p>
      </div>
      {doc && open && createPortal(
        <div className="fixed inset-0 z-[80] flex items-end justify-center bg-slate-950/40 p-3 pb-[calc(1rem+env(safe-area-inset-bottom))] md:items-center md:p-4" onClick={() => setOpen(null)}>
          <div className="flex max-h-[80vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white text-sm shadow-xl" onClick={(event) => event.stopPropagation()} role="dialog" aria-label={doc.title}>
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
              <h2 className="text-lg font-semibold text-slate-950">{doc.title}</h2>
              <button type="button" className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" onClick={() => setOpen(null)}>关闭</button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4">
              <LegalBody id={open} />
            </div>
            <div className="border-t border-slate-100 px-5 py-3 text-right">
              <Link href={`/legal/${open}`} className="text-xs text-blue-600 underline">在完整页面打开</Link>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}

export function rememberLegalAcceptance() {
  window.localStorage.setItem('pickglobal.legal', JSON.stringify({ version: LEGAL_VERSION, at: new Date().toISOString() }))
}
