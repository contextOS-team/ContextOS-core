import { describe, expect, it } from 'vitest'
import type {
  GithubSyncStatus,
  GitlabSyncStatus,
  IntegrationStatusResponse,
  JiraSyncStatus,
  LinearSyncStatus,
  ProviderStatus,
} from '@/lib/api'
import {
  buildSourceRows,
  deriveChromeSourceState,
} from '../source-sync-state'

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

describe('source sync chrome state', () => {
  it('marks selected repo sources without a successful sync as needing sync', () => {
    const rows = buildSourceRows({
      integrations: integrationStatus({
        gitlab: provider({ status: 'connected', selected_repos_count: 1 }),
      }),
      now: new Date('2026-05-21T12:00:00Z'),
    })

    const state = deriveChromeSourceState(
      { kind: 'idle', lastUpdatedAt: new Date('2026-05-21T11:00:00Z') },
      rows
    )

    expect(state.kind).toBe('needs_sync')
    expect(rows.find((row) => row.provider === 'gitlab')).toMatchObject({
      label: 'GitLab',
      health: 'needs_sync',
      detail: 'Never synced',
    })
  })

  it('shows fresh provider sync timestamps as current source state', () => {
    const github: GithubSyncStatus = {
      repo_sync_status: {
        'org/repo': { status: 'synced', synced: 12, total: 12 },
      },
      last_sync_at: '2026-05-21T11:45:00Z',
    }
    const rows = buildSourceRows({
      integrations: integrationStatus({
        github: provider({
          status: 'connected',
          selected_repos_count: 1,
          last_sync_at: '2026-05-21T11:45:00Z',
        }),
      }),
      github,
      now: new Date('2026-05-21T12:00:00Z'),
    })

    const state = deriveChromeSourceState(
      { kind: 'idle', lastUpdatedAt: new Date('2026-05-21T07:00:00Z') },
      rows
    )

    expect(state.kind).toBe('current')
    expect(rows.find((row) => row.provider === 'github')).toMatchObject({
      label: 'GitHub',
      health: 'current',
      detail: 'Synced 15m ago',
    })
  })

  it('uses source detail progress when realtime sync progress is absent', () => {
    const gitlab: GitlabSyncStatus = {
      project_sync_status: {
        '1': { status: 'syncing', synced: 3, total: 6 },
        '2': { status: 'syncing', synced: 1, total: 4 },
      },
      total_mrs: 0,
      total_reviews: 0,
      is_syncing: true,
      last_sync_at: '2026-05-21T11:30:00Z',
    }
    const rows = buildSourceRows({
      integrations: integrationStatus({
        gitlab: provider({
          status: 'connected',
          selected_repos_count: 2,
          last_sync_at: '2026-05-21T11:30:00Z',
        }),
      }),
      gitlab,
      now: new Date('2026-05-21T12:00:00Z'),
    })

    const state = deriveChromeSourceState(
      { kind: 'syncing', provider: 'gitlab', progress: null },
      rows
    )

    expect(state.kind).toBe('syncing')
    if (state.kind === 'syncing') {
      expect(state.progress).toBe(0.4)
    }
  })

  it('shows Jira count progress without pretending a percentage is known', () => {
    const jira: JiraSyncStatus = {
      sync_status: 'in_progress',
      issues_synced: 1,
      last_sync_at: '2026-05-21T11:30:00Z',
      issues_count: 1,
    }
    const rows = buildSourceRows({
      integrations: integrationStatus({
        jira: provider({
          status: 'connected',
          last_sync_at: '2026-05-21T11:30:00Z',
        }),
      }),
      jira,
      now: new Date('2026-05-21T12:00:00Z'),
    })

    const state = deriveChromeSourceState({ kind: 'unknown' }, rows)

    expect(state.kind).toBe('syncing')
    expect(rows.find((row) => row.provider === 'jira')).toMatchObject({
      label: 'Jira',
      health: 'syncing',
      detail: '1 issue synced',
      progress: null,
    })
  })

  it('shows Linear count progress without pretending a percentage is known', () => {
    const linear: LinearSyncStatus = {
      synced_teams: ['team-1'],
      sync_status: 'in_progress',
      tickets_synced: 1,
      last_sync_at: '2026-05-21T11:30:00Z',
      tickets_count: 1,
    }
    const rows = buildSourceRows({
      integrations: integrationStatus({
        linear: provider({
          status: 'connected',
          last_sync_at: '2026-05-21T11:30:00Z',
        }),
      }),
      linear,
      now: new Date('2026-05-21T12:00:00Z'),
    })

    const state = deriveChromeSourceState({ kind: 'unknown' }, rows)

    expect(state.kind).toBe('syncing')
    expect(rows.find((row) => row.provider === 'linear')).toMatchObject({
      label: 'Linear',
      health: 'syncing',
      detail: '1 ticket synced',
      progress: null,
    })
  })

  it('treats live webhook sources as current instead of stale sync work', () => {
    const rows = buildSourceRows({
      integrations: integrationStatus({
        slack: provider({ status: 'connected', selected_channels_count: 3 }),
      }),
      now: new Date('2026-05-21T12:00:00Z'),
    })

    const state = deriveChromeSourceState({ kind: 'unknown' }, rows)

    expect(state.kind).toBe('current')
    expect(rows.find((row) => row.provider === 'slack')).toMatchObject({
      label: 'Slack',
      health: 'live',
      detail: 'Live events',
    })
  })
})
