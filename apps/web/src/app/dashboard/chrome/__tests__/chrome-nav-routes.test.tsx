// @vitest-environment jsdom

import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Sidebar } from '../../sidebar'

let pathname = '/dashboard'

vi.mock('next/navigation', () => ({
  usePathname: () => pathname,
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}))

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getUser: vi.fn(async () => ({ data: { user: { id: 'user-1' } } })),
      signOut: vi.fn(async () => {}),
    },
    from: vi.fn((table: string) => {
      if (table === 'workspace_members') {
        const query = {
          select: vi.fn(() => query),
          eq: vi.fn(() => query),
          single: vi.fn(async () => ({ data: { workspace_id: 'workspace-1' }, error: null })),
        }
        return query
      }

      const query = {
        select: vi.fn(() => query),
        eq: vi.fn(() => query),
        in: vi.fn(() => query),
        order: vi.fn(() => query),
        limit: vi.fn(async () => ({
          data: [{
            event_type: 'sync_completed',
            created_at: '2026-05-20T12:00:00Z',
            metadata: { integration: 'slack' },
          }],
          error: null,
        })),
      }
      return query
    }),
    channel: vi.fn(() => {
      const channel = {
        on: vi.fn(() => channel),
        subscribe: vi.fn(() => channel),
      }
      return channel
    }),
    removeChannel: vi.fn(),
  }),
}))

describe('ChromeNav route coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: false }),
    })
  })

  for (const route of ['/dashboard', '/dashboard/context', '/dashboard/settings', '/dashboard/activity', '/dashboard/graph']) {
    it(`renders global chrome on ${route}`, async () => {
      pathname = route

      render(<Sidebar userEmail="daulet@example.com" userFullName="Daulet Ashikbayev" />)

      expect(screen.getByText('ContextOS')).toBeTruthy()
      await waitFor(() => expect(screen.getByRole('button', { name: /last synced/i })).toBeTruthy())
      expect(screen.getByTestId('avatar-puck')).toBeTruthy()
      expect(screen.getByRole('navigation').className).not.toContain('pulse-surface')
    })
  }
})
