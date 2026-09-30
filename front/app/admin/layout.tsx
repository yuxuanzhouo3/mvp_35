import type { ReactNode } from 'react'
import { AdminShell } from './components'

export default function AdminLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <AdminShell>{children}</AdminShell>
}
