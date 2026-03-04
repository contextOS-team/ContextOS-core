'use client'

import { useEffect } from 'react'

/**
 * Applies .dark class to <html> for Tailwind dark mode.
 * Dashboard is dark-only (no toggle). Paired with an inline
 * <script> in root layout for FOUC prevention.
 */
export function DarkModeApplier() {
  useEffect(() => {
    document.documentElement.classList.add('dark')
  }, [])

  return null
}
