'use client'

import { useEffect } from 'react'

function errorToMessage(value: unknown): string {
  if (value instanceof Error) return value.message
  if (typeof value === 'string') return value

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function errorToStack(value: unknown): string | undefined {
  return value instanceof Error ? value.stack : undefined
}

function postBrowserError(payload: Record<string, unknown>) {
  const body = JSON.stringify({
    href: window.location.href,
    userAgent: window.navigator.userAgent,
    ...payload,
  })

  void fetch('/api/client-errors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: body.length < 60_000,
  }).catch(() => {
    // Avoid recursion if local error logging itself fails.
  })
}

export function ClientErrorLogger() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'development') return

    function handleError(event: ErrorEvent) {
      postBrowserError({
        type: 'error',
        message: event.message || errorToMessage(event.error),
        stack: errorToStack(event.error),
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      })
    }

    function handleUnhandledRejection(event: PromiseRejectionEvent) {
      postBrowserError({
        type: 'unhandledrejection',
        message: errorToMessage(event.reason),
        stack: errorToStack(event.reason),
      })
    }

    window.addEventListener('error', handleError)
    window.addEventListener('unhandledrejection', handleUnhandledRejection)

    return () => {
      window.removeEventListener('error', handleError)
      window.removeEventListener('unhandledrejection', handleUnhandledRejection)
    }
  }, [])

  return null
}
