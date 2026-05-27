import type {
  GithubSyncStatus,
  GitlabSyncStatus,
  IntegrationStatusResponse,
  JiraSyncStatus,
  LinearSyncStatus,
  NotionSyncStatus,
  ProviderStatus,
} from '@/lib/api'
import { isWorkspaceUpdateStale, parseWorkspaceSyncDate } from '../sync-freshness'
import type { SyncState } from './use-sync-state'

export type SourceProvider =
  | 'github'
  | 'gitlab'
  | 'notion'
  | 'jira'
  | 'linear'
  | 'slack'
  | 'fathom'
  | 'telegram'

export type SourceHealth =
  | 'current'
  | 'needs_sync'
  | 'syncing'
  | 'attention'
  | 'live'
  | 'not_configured'

export type SourceRow = {
  provider: SourceProvider
  label: string
  health: SourceHealth
  detail: string
  lastSyncAt: Date | null
  progress?: number | null
}

export type ChromeSourceState =
  | { kind: 'checking'; sources: SourceRow[] }
  | { kind: 'current'; sources: SourceRow[] }
  | { kind: 'needs_sync'; sources: SourceRow[]; staleSources: SourceRow[] }
  | { kind: 'syncing'; provider: string; progress: number | null; sources: SourceRow[] }
  | { kind: 'attention'; sources: SourceRow[]; attentionSources: SourceRow[]; message: string }

type StatusMapRow = {
  status?: string
  synced?: number
  total?: number
  error_message?: string | null
}

type SourceRowsInput = {
  integrations: IntegrationStatusResponse
  github?: GithubSyncStatus | null
  gitlab?: GitlabSyncStatus | null
  notion?: NotionSyncStatus | null
  jira?: JiraSyncStatus | null
  linear?: LinearSyncStatus | null
  now?: Date
}

const PROVIDER_LABELS: Record<SourceProvider, string> = {
  github: 'GitHub',
  gitlab: 'GitLab',
  notion: 'Notion',
  jira: 'Jira',
  linear: 'Linear',
  slack: 'Slack',
  fathom: 'Fathom',
  telegram: 'Telegram',
}

const SYNCING_STATUSES = new Set(['queued', 'running', 'syncing', 'in_progress'])
const ATTENTION_STATUSES = new Set(['error', 'failed', 'timeout'])

export function formatProviderName(provider: string): string {
  const normalized = provider.toLowerCase() as SourceProvider
  return PROVIDER_LABELS[normalized] ?? provider
}

export function formatShortRelativeSyncTime(date: Date, now: Date = new Date()): string {
  const diffMs = Math.max(0, now.getTime() - date.getTime())
  const diffMin = Math.floor(diffMs / 60_000)
  const diffHours = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) return `${diffDays}d ago`
  if (diffHours > 0) return `${diffHours}h ago`
  return `${diffMin}m ago`
}

export function progressFromStatusMap(
  statusMap: Record<string, StatusMapRow>
): number | null {
  const values = Object.values(statusMap)
  const total = values.reduce((sum, row) => sum + Math.max(0, row.total ?? 0), 0)
  if (total <= 0) return null

  const synced = values.reduce((sum, row) => {
    const rowTotal = Math.max(0, row.total ?? 0)
    return sum + Math.max(0, Math.min(row.synced ?? 0, rowTotal))
  }, 0)

  return Math.max(0, Math.min(1, synced / total))
}

function isConnected(status: ProviderStatus): boolean {
  return status.status === 'connected'
}

function normalizedStatus(value?: string | null): string {
  return (value ?? '').toLowerCase()
}

function syncedCountDetail(count: number, singular: string): string {
  return `${count} ${count === 1 ? singular : `${singular}s`} synced`
}

function hasAnyStatus(
  statusMap: Record<string, StatusMapRow> | undefined,
  statuses: Set<string>
): boolean {
  if (!statusMap) return false
  return Object.values(statusMap).some((row) => statuses.has(normalizedStatus(row.status)))
}

function firstAttentionDetail(
  statusMap: Record<string, StatusMapRow> | undefined
): string | null {
  if (!statusMap) return null
  for (const row of Object.values(statusMap)) {
    if (!ATTENTION_STATUSES.has(normalizedStatus(row.status))) continue
    const message = row.error_message?.trim()
    if (message) return message
  }
  return null
}

function syncedDetail(lastSyncAt: Date | null, now: Date): string {
  if (!lastSyncAt) return 'Never synced'
  return `Synced ${formatShortRelativeSyncTime(lastSyncAt, now)}`
}

function staleDetail(lastSyncAt: Date | null, now: Date): string {
  if (!lastSyncAt) return 'Never synced'
  return `Last sync ${formatShortRelativeSyncTime(lastSyncAt, now)}`
}

function baseSyncHealth(lastSyncAt: Date | null, now: Date): Pick<SourceRow, 'health' | 'detail'> {
  if (!lastSyncAt) return { health: 'needs_sync', detail: 'Never synced' }
  if (isWorkspaceUpdateStale(lastSyncAt, now)) {
    return { health: 'needs_sync', detail: staleDetail(lastSyncAt, now) }
  }
  return { health: 'current', detail: syncedDetail(lastSyncAt, now) }
}

function codeProviderRow({
  provider,
  selectedCount,
  integrationStatus,
  statusMap,
  lastSyncAt,
  isSyncing,
  now,
}: {
  provider: 'github' | 'gitlab'
  selectedCount: number
  integrationStatus: ProviderStatus
  statusMap?: Record<string, StatusMapRow>
  lastSyncAt: Date | null
  isSyncing?: boolean
  now: Date
}): SourceRow | null {
  if (integrationStatus.status === 'error') {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'attention',
      detail: 'Reconnect source',
      lastSyncAt,
    }
  }

  if (!isConnected(integrationStatus)) return null

  if (selectedCount <= 0) {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'not_configured',
      detail: provider === 'github' ? 'No repos selected' : 'No projects selected',
      lastSyncAt,
    }
  }

  const syncProgress = statusMap ? progressFromStatusMap(statusMap) : null
  const sourceIsSyncing = isSyncing || hasAnyStatus(statusMap, SYNCING_STATUSES)
  const hasAttention = hasAnyStatus(statusMap, ATTENTION_STATUSES)
  const attentionDetail = firstAttentionDetail(statusMap)
  if (hasAttention && (!sourceIsSyncing || syncProgress === 1)) {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'attention',
      detail: attentionDetail ?? 'Sync needs attention',
      lastSyncAt,
    }
  }

  if (sourceIsSyncing && syncProgress === 1 && lastSyncAt) {
    const health = baseSyncHealth(lastSyncAt, now)
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      ...health,
      lastSyncAt,
    }
  }

  if (sourceIsSyncing) {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'syncing',
      detail: 'Syncing',
      lastSyncAt,
      progress: syncProgress,
    }
  }

  if (hasAttention) {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'attention',
      detail: attentionDetail ?? 'Sync needs attention',
      lastSyncAt,
    }
  }

  const health = baseSyncHealth(lastSyncAt, now)
  return {
    provider,
    label: PROVIDER_LABELS[provider],
    ...health,
    lastSyncAt,
  }
}

function timestampedSourceRow({
  provider,
  integrationStatus,
  lastSyncAt,
  syncStatus,
  progress,
  progressDetail,
  attentionDetail,
  now,
}: {
  provider: 'notion' | 'jira'
  integrationStatus: ProviderStatus
  lastSyncAt: Date | null
  syncStatus?: string | null
  progress?: number | null
  progressDetail?: string | null
  attentionDetail?: string | null
  now: Date
}): SourceRow | null {
  if (integrationStatus.status === 'error') {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'attention',
      detail: 'Reconnect source',
      lastSyncAt,
    }
  }

  if (!isConnected(integrationStatus)) return null

  const status = normalizedStatus(syncStatus)
  if (SYNCING_STATUSES.has(status)) {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'syncing',
      detail: progressDetail ?? 'Syncing',
      lastSyncAt,
      progress: progress ?? null,
    }
  }

  if (ATTENTION_STATUSES.has(status)) {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'attention',
      detail: attentionDetail?.trim() || 'Sync needs attention',
      lastSyncAt,
    }
  }

  const health = baseSyncHealth(lastSyncAt, now)
  return {
    provider,
    label: PROVIDER_LABELS[provider],
    ...health,
    lastSyncAt,
  }
}

function linearSourceRow({
  integrationStatus,
  linear,
  now,
}: {
  integrationStatus: ProviderStatus
  linear?: LinearSyncStatus | null
  now: Date
}): SourceRow | null {
  if (integrationStatus.status === 'error') {
    return {
      provider: 'linear',
      label: 'Linear',
      health: 'attention',
      detail: 'Reconnect source',
      lastSyncAt: null,
    }
  }

  if (!isConnected(integrationStatus)) return null

  if (!linear) {
    return {
      provider: 'linear',
      label: 'Linear',
      health: 'attention',
      detail: 'Status unavailable',
      lastSyncAt: null,
    }
  }

  const lastSyncAt = parseWorkspaceSyncDate(linear.last_sync_at)
  const status = normalizedStatus(linear.sync_status)

  if (SYNCING_STATUSES.has(status)) {
    return {
      provider: 'linear',
      label: 'Linear',
      health: 'syncing',
      detail: linear.tickets_synced > 0
        ? syncedCountDetail(linear.tickets_synced, 'ticket')
        : 'Syncing',
      lastSyncAt,
      progress: null,
    }
  }

  if (ATTENTION_STATUSES.has(status)) {
    return {
      provider: 'linear',
      label: 'Linear',
      health: 'attention',
      detail: 'Sync needs attention',
      lastSyncAt,
    }
  }

  if (linear.synced_teams.length === 0) {
    return {
      provider: 'linear',
      label: 'Linear',
      health: 'not_configured',
      detail: 'No teams selected',
      lastSyncAt,
    }
  }

  const health = baseSyncHealth(lastSyncAt, now)
  return {
    provider: 'linear',
    label: 'Linear',
    ...health,
    lastSyncAt,
  }
}

function liveSourceRow(
  provider: 'slack' | 'fathom' | 'telegram',
  status: ProviderStatus,
  detail: string
): SourceRow | null {
  if (status.status === 'error') {
    return {
      provider,
      label: PROVIDER_LABELS[provider],
      health: 'attention',
      detail: 'Reconnect source',
      lastSyncAt: null,
    }
  }

  if (!isConnected(status)) return null

  return {
    provider,
    label: PROVIDER_LABELS[provider],
    health: 'live',
    detail,
    lastSyncAt: null,
  }
}

export function buildSourceRows({
  integrations,
  github,
  gitlab,
  notion,
  jira,
  linear,
  now = new Date(),
}: SourceRowsInput): SourceRow[] {
  return [
    codeProviderRow({
      provider: 'github',
      selectedCount: integrations.github.selected_repos_count ?? 0,
      integrationStatus: integrations.github,
      statusMap: github?.repo_sync_status,
      lastSyncAt: parseWorkspaceSyncDate(github?.last_sync_at ?? integrations.github.last_sync_at),
      now,
    }),
    codeProviderRow({
      provider: 'gitlab',
      selectedCount: integrations.gitlab.selected_repos_count ?? 0,
      integrationStatus: integrations.gitlab,
      statusMap: gitlab?.project_sync_status,
      lastSyncAt: parseWorkspaceSyncDate(gitlab?.last_sync_at ?? integrations.gitlab.last_sync_at),
      isSyncing: gitlab?.is_syncing,
      now,
    }),
    timestampedSourceRow({
      provider: 'notion',
      integrationStatus: integrations.notion,
      lastSyncAt: parseWorkspaceSyncDate(notion?.last_sync_at ?? integrations.notion.last_sync_at),
      syncStatus: notion?.sync_status,
      progress: notion?.sync_total
        ? Math.max(0, Math.min(1, (notion.sync_progress ?? notion.pages_count ?? 0) / notion.sync_total))
        : null,
      attentionDetail: notion?.sync_error,
      now,
    }),
    timestampedSourceRow({
      provider: 'jira',
      integrationStatus: integrations.jira,
      lastSyncAt: parseWorkspaceSyncDate(jira?.last_sync_at ?? integrations.jira.last_sync_at),
      syncStatus: jira?.sync_status,
      progressDetail: jira && jira.issues_synced > 0
        ? syncedCountDetail(jira.issues_synced, 'issue')
        : null,
      now,
    }),
    linearSourceRow({ integrationStatus: integrations.linear, linear, now }),
    liveSourceRow('slack', integrations.slack, 'Live events'),
    liveSourceRow('fathom', integrations.fathom, 'Live meetings'),
    liveSourceRow('telegram', integrations.telegram, 'Live chats'),
  ].filter((row): row is SourceRow => Boolean(row))
}

export function deriveChromeSourceState(
  eventState: SyncState,
  sources: SourceRow[]
): ChromeSourceState {
  if (eventState.kind === 'syncing') {
    const provider = eventState.provider.toLowerCase()
    const source = sources.find((row) => row.provider === provider)
    if (!source || source.health === 'syncing') {
      return {
        kind: 'syncing',
        provider: eventState.provider,
        progress: eventState.progress ?? source?.progress ?? null,
        sources,
      }
    }
  }

  const syncingSource = sources.find((row) => row.health === 'syncing')
  if (syncingSource) {
    return {
      kind: 'syncing',
      provider: syncingSource.provider,
      progress: syncingSource.progress ?? null,
      sources,
    }
  }

  if (eventState.kind === 'error') {
    return {
      kind: 'attention',
      sources,
      attentionSources: sources.filter((row) => row.health === 'attention'),
      message: `${formatProviderName(eventState.provider)} sync paused`,
    }
  }

  const attentionSources = sources.filter((row) => row.health === 'attention')
  if (attentionSources.length > 0) {
    return {
      kind: 'attention',
      sources,
      attentionSources,
      message: `${attentionSources[0].label} needs attention`,
    }
  }

  const staleSources = sources.filter((row) => row.health === 'needs_sync')
  if (staleSources.length > 0) {
    return { kind: 'needs_sync', sources, staleSources }
  }

  return { kind: 'current', sources }
}
