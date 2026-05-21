'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  fetchGithubSyncStatus,
  fetchGitlabSyncStatus,
  fetchIntegrationStatus,
  fetchJiraSyncStatus,
  fetchLinearSyncStatus,
  fetchNotionSyncStatus,
  type GithubSyncStatus,
  type GitlabSyncStatus,
  type IntegrationStatusResponse,
  type JiraSyncStatus,
  type LinearSyncStatus,
  type NotionSyncStatus,
} from '@/lib/api'
import {
  buildSourceRows,
  deriveChromeSourceState,
  type ChromeSourceState,
  type SourceRow,
} from './source-sync-state'
import { useSyncState } from './use-sync-state'

const IDLE_REFRESH_MS = 60_000
const ACTIVE_REFRESH_MS = 3_000
const REQUEST_WAKE_MS = 60_000

type SourceSyncStateController = {
  state: ChromeSourceState
  notifySyncRequested: () => void
}

async function optionalFetch<T>(fetcher: () => Promise<T>): Promise<T | null> {
  try {
    return await fetcher()
  } catch {
    return null
  }
}

function hasConnectedProvider(
  integrations: IntegrationStatusResponse,
  provider: keyof IntegrationStatusResponse
): boolean {
  return integrations[provider].status === 'connected'
}

function sourceRowSignature(row: SourceRow): string {
  return JSON.stringify([
    row.provider,
    row.health,
    row.detail,
    row.lastSyncAt?.getTime() ?? '',
    row.progress ?? '',
  ])
}

function sourceStateSignature(state: ChromeSourceState): string {
  const sources = state.sources.map(sourceRowSignature).join('|')

  switch (state.kind) {
    case 'syncing':
      return `${state.kind}:${state.provider}:${state.progress ?? ''}:${sources}`
    case 'attention':
      return `${state.kind}:${state.message}:${sources}`
    case 'needs_sync':
    case 'current':
    case 'checking':
      return `${state.kind}:${sources}`
  }
}

export function useSourceSyncState(workspaceId: string | null): SourceSyncStateController {
  const eventState = useSyncState(workspaceId)
  const [state, setState] = useState<ChromeSourceState>({
    kind: 'checking',
    sources: [],
  })
  const [wakeUntilMs, setWakeUntilMs] = useState(0)

  const notifySyncRequested = useCallback(() => {
    setWakeUntilMs(Date.now() + REQUEST_WAKE_MS)
  }, [])

  useEffect(() => {
    if (!workspaceId) {
      setState({ kind: 'checking', sources: [] })
      return
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    async function load() {
      try {
        const integrations = await fetchIntegrationStatus()
        const [
          github,
          gitlab,
          notion,
          jira,
          linear,
        ] = await Promise.all([
          hasConnectedProvider(integrations, 'github')
            ? optionalFetch<GithubSyncStatus>(fetchGithubSyncStatus)
            : Promise.resolve(null),
          hasConnectedProvider(integrations, 'gitlab')
            ? optionalFetch<GitlabSyncStatus>(fetchGitlabSyncStatus)
            : Promise.resolve(null),
          hasConnectedProvider(integrations, 'notion')
            ? optionalFetch<NotionSyncStatus>(fetchNotionSyncStatus)
            : Promise.resolve(null),
          hasConnectedProvider(integrations, 'jira')
            ? optionalFetch<JiraSyncStatus>(fetchJiraSyncStatus)
            : Promise.resolve(null),
          hasConnectedProvider(integrations, 'linear')
            ? optionalFetch<LinearSyncStatus>(fetchLinearSyncStatus)
            : Promise.resolve(null),
        ])

        if (cancelled) return

        const sources = buildSourceRows({
          integrations,
          github,
          gitlab,
          notion,
          jira,
          linear,
        })
        const next = deriveChromeSourceState(eventState, sources)
        setState((current) => (
          sourceStateSignature(current) === sourceStateSignature(next)
            ? current
            : next
        ))

        const shouldRefreshActively = next.kind === 'syncing' || wakeUntilMs > Date.now()
        const refreshMs = shouldRefreshActively ? ACTIVE_REFRESH_MS : IDLE_REFRESH_MS
        timer = setTimeout(load, refreshMs)
      } catch {
        if (!cancelled) {
          setState({
            kind: 'attention',
            sources: [],
            attentionSources: [],
            message: 'Source status unavailable',
          })
          timer = setTimeout(load, IDLE_REFRESH_MS)
        }
      }
    }

    void load()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [workspaceId, eventState, wakeUntilMs])

  return { state, notifySyncRequested }
}
