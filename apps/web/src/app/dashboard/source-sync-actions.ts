'use client'

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
import { isWorkspaceUpdateStale, parseWorkspaceSyncDate } from './sync-freshness'

type SourceSyncTask = {
  label: string
  run: () => Promise<unknown>
}

export type SourceSyncProgress = {
  message: string
  progress: number | null
}

function isConnected(status: ProviderStatus): boolean {
  return status.status === 'connected'
}

function needsRefresh(status: ProviderStatus): boolean {
  if (!isConnected(status)) return false
  if (!status.last_sync_at) return true
  return isWorkspaceUpdateStale(parseWorkspaceSyncDate(status.last_sync_at))
}

function formatSyncLabel(provider: string): string {
  return `Checking ${provider.toLowerCase()} for changes`
}

async function collectSourceSyncTasks(
  statuses: IntegrationStatusResponse,
  onProgress: (progress: SourceSyncProgress) => void
): Promise<SourceSyncTask[]> {
  const tasks: SourceSyncTask[] = []

  if (needsRefresh(statuses.notion)) {
    tasks.push({ label: 'Notion', run: resyncNotion })
  }

  if (needsRefresh(statuses.github) && (statuses.github.selected_repos_count ?? 0) > 0) {
    tasks.push({ label: 'GitHub', run: triggerGithubSync })
  }

  if (needsRefresh(statuses.gitlab) && (statuses.gitlab.selected_repos_count ?? 0) > 0) {
    tasks.push({ label: 'GitLab', run: triggerGitlabSync })
  }

  if (needsRefresh(statuses.jira)) {
    tasks.push({ label: 'Jira', run: () => triggerJiraSync() })
  }

  if (isConnected(statuses.linear)) {
    onProgress({ message: 'Checking linear teams', progress: 0.18 })
    const linear = await fetchLinearSyncStatus().catch(() => null)
    const teamIds = linear?.synced_teams ?? []
    const linearNeedsRefresh = !linear?.last_sync_at
      || isWorkspaceUpdateStale(parseWorkspaceSyncDate(linear.last_sync_at))

    if (teamIds.length > 0 && linearNeedsRefresh) {
      tasks.push({ label: 'Linear', run: () => triggerLinearSync(teamIds) })
    }
  }

  return tasks
}

export async function triggerStaleSourceSyncs(
  onProgress: (progress: SourceSyncProgress) => void
): Promise<{ started: string[]; failed: string[] }> {
  onProgress({ message: 'Checking connected sources', progress: 0.08 })
  const statuses = await fetchIntegrationStatus()
  onProgress({ message: 'Preparing source sync', progress: 0.16 })

  const tasks = await collectSourceSyncTasks(statuses, onProgress)
  if (tasks.length === 0) return { started: [], failed: [] }

  const started: string[] = []
  const failed: string[] = []

  for (const [index, task] of tasks.entries()) {
    const baseProgress = 0.22 + (index / tasks.length) * 0.68
    onProgress({ message: formatSyncLabel(task.label), progress: baseProgress })

    try {
      await task.run()
      started.push(task.label)
    } catch {
      failed.push(task.label)
    }

    onProgress({
      message: formatSyncLabel(task.label),
      progress: 0.22 + ((index + 1) / tasks.length) * 0.68,
    })
  }

  if (started.length === 0 && failed.length > 0) {
    throw new Error(`Could not start sync for ${failed.join(', ')}`)
  }

  return { started, failed }
}

export function sourceSyncSummary(started: string[]): string {
  if (started.length === 0) return 'Sources are already current.'
  if (started.length === 1) return `${started[0]} sync started.`
  if (started.length === 2) return `${started[0]} and ${started[1]} sync started.`
  return `${started.slice(0, -1).join(', ')} and ${started[started.length - 1]} sync started.`
}
