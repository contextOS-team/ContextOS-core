// @vitest-environment jsdom

import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchIntegrationStatus } from '@/lib/api'
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

vi.mock('@/lib/api', () => ({
  fetchIntegrationStatus: vi.fn(),
  fetchGithubSyncStatus: vi.fn(),
  fetchGitlabSyncStatus: vi.fn(),
  fetchNotionSyncStatus: vi.fn(),
  fetchJiraSyncStatus: vi.fn(),
  fetchLinearSyncStatus: vi.fn(),
  resyncNotion: vi.fn(),
  triggerGithubSync: vi.fn(),
  triggerGitlabSync: vi.fn(),
  triggerJiraSync: vi.fn(),
  triggerLinearSync: vi.fn(),
}))

describe('ChromeNav route coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchIntegrationStatus).mockResolvedValue({
      linear: { status: 'disconnected', external_name: null, connected_at: null },
      slack: { status: 'disconnected', external_name: null, connected_at: null },
      fathom: { status: 'disconnected', external_name: null, connected_at: null },
      github: { status: 'disconnected', external_name: null, connected_at: null },
      gitlab: { status: 'disconnected', external_name: null, connected_at: null },
      notion: { status: 'disconnected', external_name: null, connected_at: null },
      telegram: { status: 'disconnected', external_name: null, connected_at: null },
      jira: { status: 'disconnected', external_name: null, connected_at: null },
    })
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: false }),
    })
  })

  for (const route of ['/dashboard', '/dashboard/decisions', '/dashboard/decisions/decision-1', '/dashboard/context', '/dashboard/settings', '/dashboard/activity', '/dashboard/graph']) {
    it(`renders global chrome on ${route}`, async () => {
      pathname = route

      render(<Sidebar userEmail="daulet@example.com" userFullName="Daulet Ashikbayev" />)

      expect(screen.getByText('ContextOS')).toBeTruthy()
      await waitFor(() => expect(screen.getByText(/sources current|needs sync/i)).toBeTruthy())
      expect(screen.queryByText(/updated/i)).toBeNull()
      expect(screen.getByTestId('avatar-puck')).toBeTruthy()
      expect(screen.getByRole('navigation').className).not.toContain('pulse-surface')
    })
  }
})
