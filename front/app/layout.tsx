import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'PickGlobal｜选品分析与出海获客全链路闭环',
  description: 'PickGlobal 将商品分析、海外客户发现、AI 营销触达与流失召回整合到一个工作台。',
  generator: 'PickGlobal',
}

export const viewport: Viewport = {
  colorScheme: 'light',
  themeColor: '#f7f9fc',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN" className="bg-background"><body className="antialiased">{children}</body></html>
}
