import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { LegalBody } from '@/components/legal-consent'
import { docIds, isDocId, legalDocs, legalTarget, type DocId } from '@/lib/legal-docs'

export function generateStaticParams() {
  return docIds.map((id) => ({ id }))
}

export default async function LegalPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const target = legalTarget(id)
  if (!target) notFound()
  if (!isDocId(id)) redirect(`/legal/${target}`)
  const doc = legalDocs[id]
  const links: DocId[] = [...docIds]
  return (
    <main className="min-h-screen bg-[#f5f7fb] px-4 py-10 text-slate-800">
      <article className="mx-auto max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
        <Link href="/login" className="text-sm text-blue-600">返回登录</Link>
        <h1 className="mt-3 text-2xl font-semibold text-slate-950">{doc.title}</h1>
        <p className="mt-2 text-sm text-slate-400">Last updated: 2026-10-04</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {links.map((item) => (
            <Link key={item} href={`/legal/${item}`} className={`rounded-full px-3 py-1 text-xs font-semibold ${item === id ? 'bg-blue-600 text-white' : 'border border-slate-200 bg-white text-slate-600'}`}>{legalDocs[item].title}</Link>
          ))}
        </div>
        <div className="mt-6">
          <LegalBody id={id} />
        </div>
      </article>
    </main>
  )
}
