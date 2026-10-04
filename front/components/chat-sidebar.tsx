'use client'

import { FormEvent, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { AdSlot } from '@/components/ad-slot'
import { api } from '@/lib/api'

type Conversation = { id: string; title?: string }
type ChatMessage = { id: string; role: string; content: string }

export function ChatSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [conversationId, setConversationId] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const thread = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    api<{ items: Conversation[] }>('/chat/conversations')
      .then(async (page) => {
        const current = page.items[0]
        if (!current || cancelled) return
        setConversationId(current.id)
        const history = await api<{ items: ChatMessage[] }>(`/chat/conversations/${current.id}/messages`)
        if (!cancelled) setMessages([...history.items].reverse())
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight })
  }, [messages, open])

  async function send(event: FormEvent) {
    event.preventDefault()
    const content = draft.trim()
    if (!content || sending) return
    setSending(true)
    setError('')
    setDraft('')
    try {
      let id = conversationId
      if (!id) {
        const created = await api<Conversation>('/chat/conversations', { method: 'POST', body: JSON.stringify({ title: '业务助手' }) })
        id = created.id
        setConversationId(id)
      }
      const turn = await api<{ user: ChatMessage; assistant: ChatMessage }>(`/chat/conversations/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      })
      setMessages((current) => [...current, turn.user, turn.assistant])
    } catch (reason) {
      setDraft(content)
      setError(reason instanceof Error ? reason.message : '发送失败')
    } finally {
      setSending(false)
    }
  }

  if (!open) return null

  return (
    <aside className="fixed inset-x-0 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] top-[calc(3.5rem+env(safe-area-inset-top))] z-30 flex flex-col border-t border-border bg-background md:inset-x-auto md:bottom-0 md:right-0 md:top-[calc(4rem+env(safe-area-inset-top))] md:w-80 md:border-l md:border-t-0" aria-label="对话侧栏">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <p className="text-sm font-semibold">业务助手</p>
          <p className="text-xs text-muted-foreground">解释最近的报告，金额仍由规则引擎计算</p>
        </div>
        <button type="button" className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="关闭对话" onClick={onClose}>
          <X className="size-4" />
        </button>
      </div>
      <div ref={thread} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && <p className="text-sm leading-6 text-muted-foreground">问问最近一份报告的利润和风险。</p>}
        {messages.map((message) => (
          <p key={message.id} className={`max-w-full rounded-2xl px-3 py-2 text-sm leading-6 ${message.role === 'user' ? 'ml-6 bg-primary text-primary-foreground' : 'mr-6 bg-muted text-foreground'}`}>
            {message.content}
          </p>
        ))}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
      <div className="border-t border-border px-4 py-3">
        <AdSlot placement="copilot_sidebar" className="mb-3 px-3 py-3" />
        <form onSubmit={send} className="flex gap-2">
          <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="输入问题" className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm" />
          <button type="submit" disabled={sending || !draft.trim()} className="shrink-0 rounded-xl bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50">发送</button>
        </form>
      </div>
    </aside>
  )
}
