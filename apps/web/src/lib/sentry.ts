/**
 * Sentry client-side initialization for Next.js.
 *
 * Initializes the Sentry SDK for browser error tracking and performance
 * monitoring. No-op if NEXT_PUBLIC_SENTRY_DSN is not set (safe for local dev).
 *
 * Call `initSentry()` once at app startup (e.g., in layout.tsx).
 * Sentry.init() is idempotent -- safe to call multiple times.
 */

import * as Sentry from '@sentry/nextjs'

let initialized = false

export function initSentry(): void {
  if (initialized) return

  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN
  if (!dsn) {
    // No DSN configured -- Sentry disabled (expected in local dev)
    return
  }

  const isDev = process.env.NODE_ENV === 'development'

  Sentry.init({
    dsn,
    tracesSampleRate: isDev ? 1.0 : 0.2,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    environment: process.env.NODE_ENV,
    // Source maps uploaded in CI, not during local dev
    debug: false,
  })

  initialized = true
}
