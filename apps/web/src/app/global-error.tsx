'use client'

/**
 * Next.js App Router global error boundary.
 *
 * Catches unhandled errors in the application and reports them to Sentry.
 * Renders a fallback UI with a "Try again" button to reset the error state.
 *
 * This file MUST be at `app/global-error.tsx` for Next.js to use it as the
 * root error boundary (wraps the entire app including layout).
 */

import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Report the error to Sentry
    Sentry.captureException(error)
  }, [error])

  return (
    <html lang="en">
      <body>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            padding: '2rem',
            textAlign: 'center',
          }}
        >
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            Something went wrong
          </h1>
          <p style={{ color: '#666', marginBottom: '1.5rem', maxWidth: '400px' }}>
            An unexpected error occurred. The error has been reported to our team.
          </p>
          <button
            onClick={reset}
            style={{
              padding: '0.5rem 1.5rem',
              backgroundColor: '#000',
              color: '#fff',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: 500,
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  )
}
