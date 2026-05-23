// @vitest-environment jsdom

import { render, screen, waitFor } from '@testing-library/react'
import { createElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { triggerStaleSourceSyncs } from '../../source-sync-actions'
import { SyncIndicator } from '../sync-indicator'

vi.mock('../../source-sync-actions', () => ({
  sourceSyncSummary: (started: string[]) => (
    started.length === 0 ? 'Sources are already current.' : `${started.join(', ')} sync started.`
  ),
  triggerStaleSourceSyncs: vi.fn(),
}))

describe('SyncIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-20T12:04:00Z'))
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: false }),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('renders current source state without update timestamp copy', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'current', sources: [] },
    }))

    expect(screen.queryByText(/updated/i)).toBeNull()
    expect(screen.getByText('Sources current')).toBeTruthy()
    expect(screen.getByLabelText(/workspace sources current/i)).toBeTruthy()
    expect(screen.getByTestId('sync-indicator-label').className).toContain('chrome-sync-inline')
  })

  it('auto-starts stale source state as syncing status', async () => {
    vi.useRealTimers()
    vi.mocked(triggerStaleSourceSyncs).mockImplementation((onProgress) => {
      onProgress({ message: 'Checking connected sources', progress: 0.08 })
      return new Promise(() => {})
    })

    render(createElement(SyncIndicator, {
      state: {
        kind: 'needs_sync',
        sources: [{
          provider: 'github',
          label: 'GitHub',
          health: 'needs_sync',
          detail: 'Never synced',
          lastSyncAt: null,
        }],
        staleSources: [{
          provider: 'github',
          label: 'GitHub',
          health: 'needs_sync',
          detail: 'Never synced',
          lastSyncAt: null,
        }],
      },
    }))

    expect(screen.queryByText(/updated/i)).toBeNull()
    expect(await screen.findByText('Syncing sources')).toBeTruthy()
    expect(screen.getByLabelText(/syncing sources 8%/i)).toBeTruthy()
    expect(triggerStaleSourceSyncs).toHaveBeenCalledTimes(1)
  })

  it('renders syncing progress as compact chrome status with percent', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'syncing', provider: 'slack', progress: 0.35, sources: [] },
    }))

    expect(screen.getByText('Syncing Slack')).toBeTruthy()
    expect(screen.getByText('35%')).toBeTruthy()
    expect(screen.getByLabelText('syncing slack 35%')).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: /syncing slack/i }).getAttribute('aria-valuenow'))
      .toBe('35')
    const fill = screen.getByTestId('sync-progress-fill')
    expect(fill.style.width).toBe('35%')
  })

  it('uses an indeterminate rail when no real percentage is available', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'syncing', provider: 'linear', progress: null, sources: [] },
    }))

    expect(screen.getByText('Syncing Linear')).toBeTruthy()
    expect(screen.queryByText(/%/)).toBeNull()
    expect(screen.getByRole('progressbar', { name: /syncing linear/i }).getAttribute('aria-valuenow'))
      .toBeNull()
    expect(screen.getByTestId('sync-progress-fill').className).toContain('chrome-sync-fill--indeterminate')
  })

  it('renders error copy without reconnect affordance', () => {
    render(createElement(SyncIndicator, {
      state: {
        kind: 'attention',
        sources: [],
        attentionSources: [],
        message: 'OAuth token expired',
      },
    }))

    expect(screen.getByLabelText(/workspace sources need attention/i).textContent).toBe('Needs attention')
    expect(screen.queryByText('reconnect')).toBeNull()
  })

  it('auto-starts sync for stale sources without showing a manual action', async () => {
    vi.useRealTimers()
    const onSyncRequested = vi.fn()
    let finishSync!: (value: { started: string[]; failed: string[] }) => void
    vi.mocked(triggerStaleSourceSyncs).mockImplementation((onProgress) => {
      onProgress({ message: 'Checking connected sources', progress: 0.08 })
      return new Promise((resolve) => {
        finishSync = resolve
      })
    })

    render(createElement(SyncIndicator, {
      state: {
        kind: 'needs_sync',
        sources: [{
          provider: 'jira',
          label: 'Jira',
          health: 'needs_sync',
          detail: 'Last sync 8h ago',
          lastSyncAt: new Date('2026-05-20T04:00:00Z'),
        }],
        staleSources: [{
          provider: 'jira',
          label: 'Jira',
          health: 'needs_sync',
          detail: 'Last sync 8h ago',
          lastSyncAt: new Date('2026-05-20T04:00:00Z'),
        }],
      },
      onSyncRequested,
    }))

    expect(await screen.findByText('Syncing sources')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /sync stale sources/i })).toBeNull()
    expect(triggerStaleSourceSyncs).toHaveBeenCalledTimes(1)

    finishSync({ started: ['Jira'], failed: [] })
    await waitFor(() => expect(onSyncRequested).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('progressbar', { name: /syncing sources/i }).getAttribute('aria-valuenow'))
      .toBeNull()
  })
})
