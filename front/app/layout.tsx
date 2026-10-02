import type { Metadata, Viewport } from 'next'
import { FingerScale } from '@/components/finger-scale'
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
  return <html lang="zh-CN" className="bg-background"><body className="antialiased"><FingerScale />{children}</body></html>
}
