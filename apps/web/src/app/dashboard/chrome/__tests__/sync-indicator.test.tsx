// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { createElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SyncIndicator } from '../sync-indicator'

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

  it('renders idle state as short tabular updated copy', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'idle', lastUpdatedAt: new Date('2026-05-20T12:00:00Z') },
    }))

    expect(screen.queryByRole('button', { name: /updated/i })).toBeNull()
    expect(screen.getByText('updated 4m ago').textContent).toMatch(/^updated 4m ago$/)
    expect(screen.getByTestId('sync-indicator-label').style.fontVariantNumeric).toBe('tabular-nums')
  })

  it('renders syncing progress without CSS interpolation', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'syncing', provider: 'slack', progress: 0.35 },
    }))

    expect(document.body.contains(screen.getByText(/^syncing slack/))).toBe(true)
    const fill = screen.getByTestId('sync-progress-fill')
    expect(fill.style.width).toBe('35%')
    expect(fill.style.transition).toBe('none')
  })

  it('renders error copy without reconnect affordance', () => {
    render(createElement(SyncIndicator, {
      state: { kind: 'error', provider: 'slack', message: 'OAuth token expired' },
    }))

    expect(screen.getByLabelText(/slack sync paused/i).textContent).toBe('slack sync paused')
    expect(screen.queryByText('reconnect')).toBeNull()
  })
})
