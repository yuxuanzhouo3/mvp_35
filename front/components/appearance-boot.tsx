'use client'

import { useEffect } from 'react'
import { applyAppearance, readAppearance } from '@/lib/appearance'

export function AppearanceBoot() {
  useEffect(() => {
    applyAppearance(readAppearance())
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    function onChange() {
      if (readAppearance().theme === 'system') applyAppearance(readAppearance())
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return null
}
