import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  fetchIntegrationStatus,
  fetchLinearSyncStatus,
  resyncNotion,
  triggerGithubSync,
  triggerGitlabSync,
  triggerJiraSync,
  triggerLinearSync,
  type IntegrationStatusResponse,
  type ProviderStatus,
} from '@/lib/api'
import {
  triggerStaleSourceSyncs,
  type SourceSyncProgress,
} from '../source-sync-actions'

vi.mock('@/lib/api', () => ({
  fetchIntegrationStatus: vi.fn(),
  fetchLinearSyncStatus: vi.fn(),
  resyncNotion: vi.fn(),
  triggerGithubSync: vi.fn(),
  triggerGitlabSync: vi.fn(),
  triggerJiraSync: vi.fn(),
  triggerLinearSync: vi.fn(),
}))

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

describe('source sync actions', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('starts GitLab sync for a selected source that has never synced', async () => {
    const progress: SourceSyncProgress[] = []
    vi.mocked(fetchIntegrationStatus).mockResolvedValue(integrationStatus({
      gitlab: provider({
        status: 'connected',
        selected_repos_count: 1,
        last_sync_at: null,
      }),
    }))
    vi.mocked(triggerGitlabSync).mockResolvedValue({ status: 'sync_started' })

    const result = await triggerStaleSourceSyncs((nextProgress) => {
      progress.push(nextProgress)
    })

    expect(fetchIntegrationStatus).toHaveBeenCalledTimes(1)
    expect(triggerGitlabSync).toHaveBeenCalledTimes(1)
    expect(resyncNotion).not.toHaveBeenCalled()
    expect(triggerGithubSync).not.toHaveBeenCalled()
    expect(triggerJiraSync).not.toHaveBeenCalled()
    expect(fetchLinearSyncStatus).not.toHaveBeenCalled()
    expect(triggerLinearSync).not.toHaveBeenCalled()
    expect(result).toEqual({ started: ['GitLab'], failed: [] })
    expect(progress.map((entry) => entry.message)).toContain('Checking gitlab for changes')
  })
})
