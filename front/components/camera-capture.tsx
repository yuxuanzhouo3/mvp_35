'use client'

import { useEffect, useRef, useState } from 'react'
import { Camera, X } from 'lucide-react'
import { isPhoneClient } from '@/lib/device'

export function CameraCapture({
  open,
  onClose,
  onCapture,
}: {
  open: boolean
  onClose: () => void
  onCapture: (file: File) => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const captureRef = useRef<HTMLInputElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const phone = typeof window !== 'undefined' && isPhoneClient()

  useEffect(() => {
    if (!open) return
    if (phone) {
      // Native camera sheet works more reliably than getUserMedia in mobile browsers / WeChat.
      const timer = window.setTimeout(() => captureRef.current?.click(), 0)
      return () => window.clearTimeout(timer)
    }
    let cancelled = false
    setError('')
    async function start() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          setError('当前环境不支持摄像头，请改用上传图片。')
          return
        }
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => undefined)
        }
      } catch {
        if (!cancelled) setError('无法打开摄像头，请检查权限后重试，或改用上传图片。')
      }
    }
    void start()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }, [open, phone])

  function takeNative(file: File | undefined) {
    if (file) onCapture(file)
    onClose()
  }

  async function snap() {
    const video = videoRef.current
    if (!video || busy) return
    setBusy(true)
    try {
      const width = video.videoWidth || 1280
      const height = video.videoHeight || 720
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) throw new Error('canvas')
      ctx.drawImage(video, 0, 0, width, height)
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
      if (!blob) throw new Error('blob')
      onCapture(new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' }))
      onClose()
    } catch {
      setError('拍照失败，请重试。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <input
        ref={captureRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(event) => {
          takeNative(event.target.files?.[0])
          event.target.value = ''
        }}
      />
      {open && !phone && (
        <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/50 p-3 sm:items-center" role="dialog" aria-label="拍照">
          <div className="w-full max-w-md overflow-hidden rounded-2xl border border-border bg-background shadow-xl">
            <div className="flex items-center justify-between gap-2 px-3 py-2">
              <p className="text-sm font-medium">拍照</p>
              <button type="button" className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted" aria-label="关闭" onClick={onClose}>
                <X className="size-4" />
              </button>
            </div>
            <div className="aspect-video bg-black">
              {!error ? (
                <video ref={videoRef} className="size-full object-cover" playsInline muted autoPlay />
              ) : (
                <div className="flex size-full flex-col items-center justify-center gap-3 px-4 text-center text-sm text-white/90">
                  <p>{error}</p>
                  <button type="button" className="rounded-xl bg-white px-3 py-2 text-sm text-foreground" onClick={() => captureRef.current?.click()}>改用系统相机</button>
                </div>
              )}
            </div>
            <div className="flex items-center justify-center gap-3 px-3 py-3">
              <button type="button" disabled={!!error || busy} className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-primary px-4 text-sm text-primary-foreground disabled:opacity-50" onClick={() => void snap()}>
                <Camera className="size-4" />
                {busy ? '处理中' : '拍照'}
              </button>
              <button type="button" className="h-10 rounded-xl border border-border px-4 text-sm" onClick={onClose}>取消</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
