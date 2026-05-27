// @vitest-environment jsdom

import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { IntegrationStatusResponse, ProviderStatus } from '@/lib/api'
import {
  DASHBOARD_REQUEST_TIMEOUT_MS,
  useDashboardData,
} from '../use-dashboard-data'

const apiMocks = vi.hoisted(() => ({
  getGithubIndexStatus: vi.fn(),
  getGithubSyncStatus: vi.fn(),
  getIntegrationStatus: vi.fn(),
  getLinearSyncStatus: vi.fn(),
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
  getGithubIndexStatus: apiMocks.getGithubIndexStatus,
  getGithubSyncStatus: apiMocks.getGithubSyncStatus,
  getIntegrationStatus: apiMocks.getIntegrationStatus,
  getLinearSyncStatus: apiMocks.getLinearSyncStatus,
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
        workspaceSnapshot: data.workspaceSnapshot.length,
      })}
    </output>
  )
}

function provider(overrides: Partial<ProviderStatus> = {}): ProviderStatus {
  return {
    status: 'disconnected',
    external_name: null,
    connected_at: null,
    ...overrides,
  }
}

function integrationStatus(
  overrides: Partial<IntegrationStatusResponse> = {}
): IntegrationStatusResponse {
  return {
    linear: provider(),
    slack: provider(),
    fathom: provider(),
    github: provider(),
    gitlab: provider(),
    notion: provider(),
    telegram: provider(),
    jira: provider(),
    ...overrides,
  }
}

function mockDefaultDashboardFetches() {
  apiMocks.getDashboardAttention.mockResolvedValue([])
  apiMocks.getDashboardSuggestions.mockResolvedValue([])
  apiMocks.getMissedDecisionReviewSuggestions.mockResolvedValue([])
  apiMocks.fetchDecisions.mockResolvedValue([])
  contextMocks.fetchContextPages.mockResolvedValue([])
  activityMocks.fetchActivityDelta.mockResolvedValue([])
  activityMocks.bucketDelta.mockReturnValue({
    decisions: { count: 0, items: [] },
    sources: { count: 0, items: [] },
    needsYou: { topUrgentItem: null, items: [] },
  })
  apiMocks.getIntegrationStatus.mockResolvedValue(integrationStatus())
  apiMocks.getLinearSyncStatus.mockResolvedValue({
    synced_teams: [],
    sync_status: null,
    tickets_synced: 0,
    tickets_count: 0,
    last_sync_at: null,
  })
  apiMocks.getGithubSyncStatus.mockResolvedValue({
    repo_sync_status: {},
    last_sync_at: null,
  })
  apiMocks.getGithubIndexStatus.mockResolvedValue({
    status: 'idle',
    last_indexed_at: null,
    repos: [],
  })
}

describe('useDashboardData', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('does not fail the dashboard when suggestions are unavailable', async () => {
    mockDefaultDashboardFetches()
    apiMocks.getDashboardSuggestions.mockRejectedValue(new Error('Failed to fetch'))
    contextMocks.fetchContextPages.mockResolvedValue([{ id: 'ctx-1' }])

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
    mockDefaultDashboardFetches()
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
    mockDefaultDashboardFetches()
    apiMocks.getDashboardSuggestions.mockReturnValue(new Promise(() => {}))
    contextMocks.fetchContextPages.mockResolvedValue([{ id: 'ctx-1' }])

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

  it('builds a first-run snapshot from imported workspace source status', async () => {
    mockDefaultDashboardFetches()
    apiMocks.getIntegrationStatus.mockResolvedValue(integrationStatus({
      linear: provider({ status: 'connected' }),
      github: provider({ status: 'connected', selected_repos_count: 1 }),
    }))
    apiMocks.getLinearSyncStatus.mockResolvedValue({
      synced_teams: ['team-1'],
      sync_status: 'complete',
      tickets_synced: 64,
      tickets_count: 64,
      last_sync_at: '2026-05-27T12:29:17Z',
    })
    apiMocks.getGithubSyncStatus.mockResolvedValue({
      repo_sync_status: {
        'contextOS-team/ContextOS-core': { status: 'synced', synced: 0, total: 0 },
      },
      last_sync_at: '2026-05-27T12:41:44Z',
    })
    apiMocks.getGithubIndexStatus.mockResolvedValue({
      status: 'idle',
      last_indexed_at: '2026-05-27T12:41:45Z',
      repos: [{ repo: 'contextOS-team/ContextOS-core', chunks: 3053 }],
    })

    render(<Probe />)

    await waitFor(() => {
      const state = JSON.parse(screenText())

      expect(state.isLoading).toBe(false)
      expect(state.workspaceSnapshot).toBe(2)
    })
  })
})

function screenText(): string {
  return screen.getByTestId('dashboard-state').textContent ?? ''
}
