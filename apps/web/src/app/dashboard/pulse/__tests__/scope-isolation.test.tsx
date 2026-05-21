// @vitest-environment jsdom

import { render } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it, vi } from 'vitest'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/dashboard',
}))

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getUser: vi.fn(async () => ({ data: { user: null } })),
    },
    from: vi.fn(() => {
      const query = {
        select: vi.fn(() => query),
        eq: vi.fn(() => query),
        maybeSingle: vi.fn(async () => ({ data: null, error: null })),
        single: vi.fn(async () => ({ data: null, error: null })),
        upsert: vi.fn(async () => ({ data: null, error: null })),
      }
      return query
    }),
  }),
}))

vi.mock('@/lib/api', () => ({
  getDashboardAttention: vi.fn(async () => []),
  fetchMyWorkGraph: vi.fn(async () => null),
}))

vi.mock('@/lib/context-feed', () => ({
  fetchContextPages: vi.fn(async () => []),
}))

vi.mock('../since-last-visit/activity-delta', () => ({
  bucketDelta: vi.fn(() => ({
    decisions: { count: 0, items: [] },
    sources: { count: 0, items: [] },
    needsYou: { topUrgentItem: null, items: [] },
  })),
  fetchActivityDelta: vi.fn(async () => []),
}))

const SUBROUTE_FILES = [
  'context/page.tsx',
  'settings/page.tsx',
  'activity/page.tsx',
  'graph/page.tsx',
]

describe('Phase 41 .pulse-surface scope isolation', () => {
  it.each(SUBROUTE_FILES)('does not apply pulse-surface in dashboard/%s', (file) => {
    // Static fallback is intentional: activity is a server component and graph
    // uses dynamic browser-only imports. The regression guard is still
    // executable and covers all sibling route files.
    const source = readFileSync(path.join(process.cwd(), 'src/app/dashboard', file), 'utf8')
    expect(source).not.toMatch(/\bpulse-surface\b/)
  })

  it('applies pulse-surface to dashboard home', async () => {
    const mod = await import('@/app/dashboard/page')
    const Component = mod.default
    const { container } = render(<Component />)
    const main = container.querySelector('main')

    expect(main).not.toBeNull()
    expect(main?.className).toMatch(/\bpulse-surface\b/)
  })
})
