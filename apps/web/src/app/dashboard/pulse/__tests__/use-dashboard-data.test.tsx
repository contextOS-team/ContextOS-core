// @vitest-environment jsdom

import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  DASHBOARD_REQUEST_TIMEOUT_MS,
  useDashboardData,
} from '../use-dashboard-data'

const apiMocks = vi.hoisted(() => ({
  getDashboardAttention: vi.fn(),
  getDashboardSuggestions: vi.fn(),
  getMissedDecisionReviewSuggestions: vi.fn(),
  fetchDecisions: vi.fn(),
  addMissedDecisionAsEvidence: vi.fn(),
  deferMissedDecision: vi.fn(),
  dismissMissedDecision: vi.fn(),
  ignoreMissedDecisionDuplicate: vi.fn(),
  saveMissedDecisionAsNewDecision: vi.fn(),
}))

const contextMocks = vi.hoisted(() => ({
  fetchContextPages: vi.fn(),
}))

const activityMocks = vi.hoisted(() => ({
  bucketDelta: vi.fn(),
  fetchActivityDelta: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  getDashboardAttention: apiMocks.getDashboardAttention,
  getDashboardSuggestions: apiMocks.getDashboardSuggestions,
  getMissedDecisionReviewSuggestions: apiMocks.getMissedDecisionReviewSuggestions,
  fetchDecisions: apiMocks.fetchDecisions,
  addMissedDecisionAsEvidence: apiMocks.addMissedDecisionAsEvidence,
  deferMissedDecision: apiMocks.deferMissedDecision,
  dismissMissedDecision: apiMocks.dismissMissedDecision,
  ignoreMissedDecisionDuplicate: apiMocks.ignoreMissedDecisionDuplicate,
  saveMissedDecisionAsNewDecision: apiMocks.saveMissedDecisionAsNewDecision,
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
  },
}))

vi.mock('@/lib/context-feed', () => ({
  fetchContextPages: contextMocks.fetchContextPages,
}))

vi.mock('../since-last-visit/activity-delta', () => ({
  bucketDelta: activityMocks.bucketDelta,
  fetchActivityDelta: activityMocks.fetchActivityDelta,
}))

function Probe() {
  const data = useDashboardData('workspace-1', null)

  return (
    <output data-testid="dashboard-state">
      {JSON.stringify({
        error: data.error,
        isLoading: data.isLoading,
        suggestions: data.suggestions.length,
        needsReviewSuggestions: data.needsReviewSuggestions.length,
        needsReviewError: data.needsReviewError,
        contextItems: data.contextItems.length,
        decisions: data.decisions?.length ?? 0,
      })}
    </output>
  )
}

describe('useDashboardData', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('does not fail the dashboard when suggestions are unavailable', async () => {
    apiMocks.getDashboardAttention.mockResolvedValue([])
    apiMocks.getDashboardSuggestions.mockRejectedValue(new Error('Failed to fetch'))
    apiMocks.getMissedDecisionReviewSuggestions.mockResolvedValue([])
    apiMocks.fetchDecisions.mockResolvedValue([])
    contextMocks.fetchContextPages.mockResolvedValue([{ id: 'ctx-1' }])
    activityMocks.fetchActivityDelta.mockResolvedValue([])
    activityMocks.bucketDelta.mockReturnValue({
      decisions: { count: 0, items: [] },
      sources: { count: 0, items: [] },
      needsYou: { topUrgentItem: null, items: [] },
    })

    render(<Probe />)

    await waitFor(() => {
      const state = JSON.parse(screenText())

      expect(state.isLoading).toBe(false)
      expect(state.error).toBeNull()
      expect(state.suggestions).toBe(0)
      expect(state.contextItems).toBe(1)
    })
  })

  it('loads workspace decisions for the home Recent decisions feed', async () => {
    apiMocks.getDashboardAttention.mockResolvedValue([])
    apiMocks.getDashboardSuggestions.mockResolvedValue([])
    apiMocks.getMissedDecisionReviewSuggestions.mockResolvedValue([])
    apiMocks.fetchDecisions.mockResolvedValue([
      {
        id: 'decision-1',
        entity_type: 'Decision',
        name: 'Approved layouts for active contractual orders in the cockpit admin',
        depth: 0,
        created_at: '2026-05-25T13:48:04Z',
        properties: { date: '2026-05-25' },
      },
    ])
    contextMocks.fetchContextPages.mockResolvedValue([])
    activityMocks.fetchActivityDelta.mockResolvedValue([])
    activityMocks.bucketDelta.mockReturnValue({
      decisions: { count: 1, items: [] },
      sources: { count: 0, items: [] },
      needsYou: { topUrgentItem: null, items: [] },
    })

    render(<Probe />)

    await waitFor(() => {
      const state = JSON.parse(screenText())

      expect(state.isLoading).toBe(false)
      expect(state.decisions).toBe(1)
      expect(apiMocks.fetchDecisions).toHaveBeenCalledWith(20)
    })
  })

  it('does not leave the dashboard loading when suggestions never settle', async () => {
    vi.useFakeTimers()
    apiMocks.getDashboardAttention.mockResolvedValue([])
    apiMocks.getDashboardSuggestions.mockReturnValue(new Promise(() => {}))
    apiMocks.getMissedDecisionReviewSuggestions.mockResolvedValue([])
    apiMocks.fetchDecisions.mockResolvedValue([])
    contextMocks.fetchContextPages.mockResolvedValue([{ id: 'ctx-1' }])
    activityMocks.fetchActivityDelta.mockResolvedValue([])
    activityMocks.bucketDelta.mockReturnValue({
      decisions: { count: 0, items: [] },
      sources: { count: 0, items: [] },
      needsYou: { topUrgentItem: null, items: [] },
    })

    render(<Probe />)

    await act(async () => {
      await Promise.resolve()
    })
    expect(JSON.parse(screenText()).isLoading).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(DASHBOARD_REQUEST_TIMEOUT_MS + 1)
    })

    const state = JSON.parse(screenText())
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.suggestions).toBe(0)
    expect(state.needsReviewSuggestions).toBe(0)
    expect(state.needsReviewError).toBeNull()
    expect(state.contextItems).toBe(1)
  })
})

function screenText(): string {
  return screen.getByTestId('dashboard-state').textContent ?? ''
}
