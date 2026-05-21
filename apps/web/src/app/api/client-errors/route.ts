import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

type ClientErrorPayload = {
  type?: unknown
  message?: unknown
  stack?: unknown
  filename?: unknown
  lineno?: unknown
  colno?: unknown
  href?: unknown
  userAgent?: unknown
}

function asBoundedString(value: unknown, maxLength: number): string | undefined {
  if (typeof value !== 'string') return undefined
  return value.slice(0, maxLength)
}

function asBoundedNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

export async function POST(request: NextRequest) {
  if (process.env.NODE_ENV !== 'development') {
    return new NextResponse(null, { status: 204 })
  }

  let payload: ClientErrorPayload
  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ error: 'invalid_json' }, { status: 400 })
  }

  const entry = {
    event: 'browser_error',
    type: asBoundedString(payload.type, 80) ?? 'unknown',
    message: asBoundedString(payload.message, 2_000) ?? 'Unknown browser error',
    stack: asBoundedString(payload.stack, 8_000),
    filename: asBoundedString(payload.filename, 1_000),
    lineno: asBoundedNumber(payload.lineno),
    colno: asBoundedNumber(payload.colno),
    href: asBoundedString(payload.href, 1_000),
    userAgent: asBoundedString(payload.userAgent, 500),
    timestamp: new Date().toISOString(),
  }

  console.error(JSON.stringify(entry))

  return new NextResponse(null, { status: 204 })
}
