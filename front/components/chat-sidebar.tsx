'use client'

import { FormEvent, useEffect, useRef, useState } from 'react'
import { Camera, Mic, MicOff, Paperclip, X } from 'lucide-react'
import { AdSlot } from '@/components/ad-slot'
import { CameraCapture } from '@/components/camera-capture'
import { CHAT_PROMPTS, PromptSuggest, usePromptKeys } from '@/components/prompt-suggest'
import { api } from '@/lib/api'
import { isPhoneClient } from '@/lib/device'

type Conversation = { id: string; title?: string }
type ChatMessage = { id: string; role: string; content: string }

type SpeechRec = {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
}

export function ChatSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [conversationId, setConversationId] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [fileName, setFileName] = useState('')
  const [recording, setRecording] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const thread = useRef<HTMLDivElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)
  const voiceFileRef = useRef<HTMLInputElement>(null)
  const speechRef = useRef<SpeechRec | null>(null)
  const draftKeys = usePromptKeys(CHAT_PROMPTS, draft, setDraft)

  function openCamera() {
    setCameraOpen(false)
    window.requestAnimationFrame(() => setCameraOpen(true))
  }

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

  useEffect(() => () => {
    speechRef.current?.stop()
  }, [])

  function attachImage(file: File | undefined) {
    if (!file || !file.type.startsWith('image/')) return
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(file)
    })
    setFileName(file.name)
    setDraft((current) => current.trim() || `请看这张图：${file.name.replace(/\.[^.]+$/, '')}`)
  }

  function clearImage() {
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setFileName('')
  }

  function toggleVoice() {
    const Speech = (window as unknown as { SpeechRecognition?: new () => SpeechRec; webkitSpeechRecognition?: new () => SpeechRec }).SpeechRecognition
      || (window as unknown as { webkitSpeechRecognition?: new () => SpeechRec }).webkitSpeechRecognition
    if (!Speech) {
      if (isPhoneClient()) {
        voiceFileRef.current?.click()
        return
      }
      setError('当前浏览器不支持语音输入，请改用文字或上传图片。')
      return
    }
    if (recording) {
      speechRef.current?.stop()
      setRecording(false)
      return
    }
    const rec = new Speech()
    rec.lang = 'zh-CN'
    rec.continuous = false
    rec.interimResults = false
    rec.onresult = (event) => {
      const text = Array.from(event.results).map((row) => row[0]?.transcript || '').join('').trim()
      if (text) setDraft((current) => (current ? `${current.trim()} ${text}` : text))
    }
    rec.onerror = () => setRecording(false)
    rec.onend = () => setRecording(false)
    speechRef.current = rec
    setRecording(true)
    rec.start()
  }

  async function send(event: FormEvent) {
    event.preventDefault()
    const content = draft.trim()
    if (!content || sending) return
    setSending(true)
    setError('')
    setDraft('')
    clearImage()
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
    <aside className="fixed inset-x-0 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] top-[calc(3rem+env(safe-area-inset-top))] z-40 flex flex-col bg-background md:inset-x-auto md:bottom-0 md:right-0 md:top-[calc(3rem+env(safe-area-inset-top))] md:w-80" aria-label="客服">
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div>
          <p className="text-sm font-semibold">客服</p>
          <p className="text-xs text-muted-foreground">大模型解释最近的报告，金额仍由规则引擎锁定</p>
        </div>
        <button type="button" className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="关闭客服" onClick={onClose}>
          <X className="size-4" />
        </button>
      </div>
      <div ref={thread} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && <p className="text-sm leading-6 text-muted-foreground">问问最近一份报告的利润和风险。Tab / 方向键可切换默认问题。</p>}
        {messages.map((message) => (
          <p key={message.id} className={`max-w-full rounded-2xl px-3 py-2 text-sm leading-6 ${message.role === 'user' ? 'ml-6 bg-primary text-primary-foreground' : 'mr-6 bg-muted text-foreground'}`}>
            {message.content}
          </p>
        ))}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
      <div className="border-t border-border px-4 py-3">
        <AdSlot placement="copilot_sidebar" className="mb-3 px-3 py-3" />
        <form onSubmit={send} className="flex flex-col gap-2">
          <input ref={uploadRef} type="file" accept="image/*" className="hidden" onChange={(event) => {
            attachImage(event.target.files?.[0])
            event.target.value = ''
          }} />
          <input ref={voiceFileRef} type="file" accept="audio/*" capture className="hidden" onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) setDraft((current) => current.trim() || `语音提问：${file.name.replace(/\.[^.]+$/, '')}`)
            event.target.value = ''
          }} />
          <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
            <div className="flex shrink-0 items-center gap-1.5">
              <button type="button" title="上传图片" aria-label="上传图片" className="flex size-10 items-center justify-center rounded-full border border-border bg-background text-foreground transition hover:bg-muted md:size-8" onClick={() => uploadRef.current?.click()}>
                <Paperclip className="size-4 md:size-3.5" />
              </button>
              <button type="button" title={recording ? '停止语音' : '语音输入'} aria-label={recording ? '停止语音' : '语音输入'} className={`hidden size-8 items-center justify-center rounded-full border transition md:flex ${recording ? 'animate-pulse border-rose-300 bg-rose-50 text-rose-600' : 'border-border bg-background text-foreground hover:bg-muted'}`} onClick={toggleVoice}>
                {recording ? <MicOff className="size-3.5" /> : <Mic className="size-3.5" />}
              </button>
              <button type="button" title="拍照" aria-label="拍照" className={`flex size-10 items-center justify-center rounded-full border transition md:size-8 ${cameraOpen ? 'border-sky-400 bg-sky-50 text-sky-700' : 'border-border bg-background text-foreground hover:bg-muted'}`} onClick={openCamera}>
                <Camera className="size-4 md:size-3.5" />
              </button>
            </div>
            <button type="submit" disabled={sending || !draft.trim()} className="ml-auto h-10 shrink-0 rounded-xl bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50 md:h-auto md:py-2">发送</button>
          </div>
          <div className="max-h-20 overflow-y-auto md:max-h-none">
            <PromptSuggest options={CHAT_PROMPTS} value={draft} onPick={setDraft} />
          </div>
          {preview && (
            <div className="flex items-center gap-2 rounded-lg border border-border bg-secondary/40 px-2 py-1.5">
              <img src={preview} alt={fileName || '参考图'} className="size-10 rounded-md object-cover" />
              <span className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">{fileName || '参考图'}</span>
              <button type="button" className="flex size-6 items-center justify-center rounded-full text-muted-foreground hover:bg-muted" onClick={clearImage} title="移除图片">
                <X className="size-3.5" />
              </button>
            </div>
          )}
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={draftKeys.onKeyDown}
            placeholder="Tab / ↑↓←→ 切换默认问题"
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
          />
          <CameraCapture open={cameraOpen} onClose={() => setCameraOpen(false)} onCapture={attachImage} />
        </form>
      </div>
    </aside>
  )
}
