'use client'

/**
 * Client component that initializes Sentry on mount.
 *
 * Included in RootLayout to ensure Sentry is initialized for all pages.
 * Renders nothing -- exists solely for the initialization side effect.
 */

import { initSentry } from '@/lib/sentry'

// Initialize Sentry eagerly at module load time (runs once on client)
initSentry()

export function SentryInit() {
  // No-op render -- Sentry was initialized at module scope above
  return null
}
