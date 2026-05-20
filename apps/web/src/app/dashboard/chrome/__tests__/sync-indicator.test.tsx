// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IntegrationDrawer } from '../integration-drawer'
import { SyncIndicator } from '../sync-indicator'

vi.mock('@/lib/api', () => ({
  getIntegrationStatus: vi.fn(async () => ({
    slack: { status: 'connected', external_name: 'ContextOS', connected_at: null },
    github: { status: 'disconnected', external_name: null, connected_at: null },
  })),
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
  })

  it('renders idle state as short tabular last-synced copy', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'idle', lastSyncedAt: new Date('2026-05-20T12:00:00Z') },
      onOpenDrawer: () => {},
    }))

    const button = screen.getByRole('button', { name: /last synced 4m ago/i })
    expect(button.textContent).toMatch(/^last synced 4m ago$/)
    expect(screen.getByTestId('sync-indicator-label').style.fontVariantNumeric).toBe('tabular-nums')
  })

  it('renders syncing progress without CSS interpolation', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'syncing', provider: 'slack', progress: 0.35 },
      onOpenDrawer: () => {},
    }))

    expect(document.body.contains(screen.getByText(/^syncing slack/))).toBe(true)
    const fill = screen.getByTestId('sync-progress-fill')
    expect(fill.style.width).toBe('35%')
    expect(fill.style.transition).toBe('none')
  })

  it('renders error copy with reconnect text', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'error', provider: 'slack', message: 'OAuth token expired' },
      onOpenDrawer: () => {},
    }))

    const button = screen.getByRole('button', { name: /slack sync paused.*reconnect/i })
    expect(button.textContent).toContain('slack sync paused')
    expect(button.textContent).toContain('reconnect')
  })

  it('opens the drawer when the cluster is clicked', async () => {
    const onOpenDrawer = vi.fn()
    render(createElement(SyncIndicator, {
      state: { kind: 'idle', lastSyncedAt: new Date('2026-05-20T12:00:00Z') },
      onOpenDrawer,
    }))

    vi.useRealTimers()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /last synced 4m ago/i }))

    expect(onOpenDrawer).toHaveBeenCalledTimes(1)
  })
})

describe('IntegrationDrawer', () => {
  it('renders nothing when closed', () => {
    render(createElement(IntegrationDrawer, {
      open: false,
      onOpenChange: () => {},
      workspaceId: 'workspace-1',
    }))

    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('renders provider rows and Sync all when open', async () => {
    render(createElement(IntegrationDrawer, {
      open: true,
      onOpenChange: () => {},
      workspaceId: 'workspace-1',
    }))

    expect(document.body.contains(await screen.findByRole('dialog'))).toBe(true)
    expect(document.body.contains(screen.getByText('Source status'))).toBe(true)
    expect(document.body.contains(screen.getByRole('button', { name: /sync all/i }))).toBe(true)
    expect(screen.queryByText(/coming soon/i)).toBeNull()
    expect(document.body.contains(screen.getByText('slack'))).toBe(true)
  })
})
