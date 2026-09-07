import type { Metadata, Viewport } from 'next'
import type { ReactNode } from 'react'
import { AdminShell } from './components'
import './globals.css'

export const metadata: Metadata = {
  title: 'PickGlobal Platform Admin',
  description: 'PickGlobal 广告、用户、行为、邀请与召回运营后台',
}

export const viewport: Viewport = {
  colorScheme: 'light',
  themeColor: '#10203f',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><AdminShell>{children}</AdminShell></body>
    </html>
  )
}
