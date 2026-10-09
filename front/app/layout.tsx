import type { Metadata, Viewport } from 'next'
import { AppearanceBoot } from '@/components/appearance-boot'
import { FingerScale } from '@/components/finger-scale'
import { PageWatch } from '@/components/page-watch'
import { APPEARANCE_BOOT } from '@/lib/appearance'
import './globals.css'

export const metadata: Metadata = {
  title: 'PickGlobal｜选品分析与出海获客全链路闭环',
  description: 'PickGlobal 把选品分析报告和九路获客成交召回放进同一个工作台。',
  generator: 'PickGlobal',
}

export const viewport: Viewport = {
  colorScheme: 'light',
  themeColor: '#f7f9fc',
  width: 'device-width',
  initialScale: 1,
  minimumScale: 1,
  maximumScale: 5,
  userScalable: true,
  viewportFit: 'cover',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className="bg-background" suppressHydrationWarning>
      <body className="antialiased">
        <script dangerouslySetInnerHTML={{ __html: APPEARANCE_BOOT }} />
        <AppearanceBoot />
        <FingerScale />
        <PageWatch />
        {children}
      </body>
    </html>
  )
}
