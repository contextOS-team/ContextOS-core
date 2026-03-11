'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  connectLinear,
  disconnectLinear,
  connectSlack,
  disconnectSlack,
  disconnectFathom,
  connectTelegram,
  disconnectTelegram,
  connectGithub,
  disconnectGithub,
  connectGitlab,
  disconnectGitlab,
  connectNotion,
  disconnectNotion,
  connectJira,
  disconnectJira,
  resyncNotion,
  getNotionSyncStatus,
  getIntegrationStatus,
  type IntegrationStatusResponse,
} from '@/lib/api'
import { displayName, formatRelativeTime } from '@/lib/utils'
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  GitLabLogo,
  FathomLogo,
  NotionLogo,
  TelegramLogo,
  JiraLogo,
} from '@/components/icons/brand-logos'
import { IntegrationCard } from '../../integrations/integration-card'
import { ticketProviderDisabledReason } from '@/lib/ticket-provider'
import { computeSyncState } from '@/lib/sync-progress'
import { SlackChannels } from '../../integrations/slack-channels'
import { FathomConnect } from '../../integrations/fathom-connect'
import { GithubRepos } from '../../integrations/github-repos'

// ---------------------------------------------------------------------------
// Telegram Connect Form
// ---------------------------------------------------------------------------

function TelegramConnect({ onConnected }: { onConnected?: () => void }) {
  const [token, setToken] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!token.trim()) {
      setError('Bot token is required')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await connectTelegram(token.trim())
      setToken('')
      onConnected?.()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to connect. Check your bot token.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="telegram-bot-token" className="text-xs">
          Bot Token
        </Label>
        <Input
          id="telegram-bot-token"
          type="password"
          placeholder="Bot token from @BotFather"
          value={token}
          onChange={(e) => {
            setToken(e.target.value)
            setError(null)
          }}
          className="h-8 text-xs"
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">
          Create a bot via @BotFather on Telegram. In Bot Settings, turn Group Privacy OFF so the bot can read all messages.
        </p>
      </div>

      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      <Button size="sm" type="submit" disabled={isLoading || !token.trim()}>
        {isLoading ? 'Connecting...' : 'Connect'}
      </Button>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Integrations Tab
// ---------------------------------------------------------------------------

export function IntegrationsTab() {
  const searchParams = useSearchParams()
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const PROVIDER_LABELS: Record<string, string> = {
      github: 'GitHub', gitlab: 'GitLab', notion: 'Notion', jira: 'Jira', linear: 'Linear',
    }
    for (const provider of ['github', 'gitlab', 'notion', 'jira', 'linear'] as const) {
      const status = searchParams.get(provider)
      if (status === 'connected') {
        setError(null)
        window.history.replaceState({}, '', '/dashboard/settings?tab=integrations')
      } else if (status === 'error') {
        const reason = searchParams.get('reason') || 'unknown'
        const label = PROVIDER_LABELS[provider] ?? provider
        const messages: Record<string, string> = {
          invalid_state: `${label} connection failed: invalid or expired session.`,
          callback_failed: `${label} connection failed. Please try again.`,
          exchange_failed: `${label} connection failed. Please try again.`,
          internal_error: `An internal error occurred during ${label} connection.`,
          provider_conflict: `Cannot connect ${label}: disconnect your current ticket provider first.`,
        }
        setError(messages[reason] || `${label} connection failed: ${reason}`)
        window.history.replaceState({}, '', '/dashboard/settings?tab=integrations')
      }
    }
  }, [searchParams])

  const fetchStatuses = useCallback(async () => {
    try {
      const data = await getIntegrationStatus()
      setStatuses(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load integrations')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatuses()
  }, [fetchStatuses])

  function makeConnectHandler(
    connectFn: () => Promise<{ authorization_url?: string; installation_url?: string }>,
    urlKey: 'authorization_url' | 'installation_url'
  ) {
    return async () => {
      try {
        const result = await connectFn()
        const url = result[urlKey]
        if (url) window.location.href = url
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start connection')
      }
    }
  }

  function makeDisconnectHandler(disconnectFn: () => Promise<unknown>, name: string) {
    return async () => {
      try {
        await disconnectFn()
      } catch (err) {
        setError(err instanceof Error ? err.message : `Failed to disconnect ${name}`)
      }
      await fetchStatuses()
    }
  }

  const handleConnectLinear = makeConnectHandler(connectLinear, 'authorization_url')
  const handleDisconnectLinear = makeDisconnectHandler(disconnectLinear, 'Linear')
  const handleConnectSlack = makeConnectHandler(connectSlack, 'authorization_url')
  const handleDisconnectSlack = makeDisconnectHandler(disconnectSlack, 'Slack')
  const handleDisconnectFathom = makeDisconnectHandler(disconnectFathom, 'Fathom')
  const handleDisconnectTelegram = makeDisconnectHandler(disconnectTelegram, 'Telegram')
  const handleConnectGithub = makeConnectHandler(connectGithub, 'installation_url')
  const handleDisconnectGithub = makeDisconnectHandler(disconnectGithub, 'GitHub')
  const handleConnectGitlab = makeConnectHandler(connectGitlab, 'authorization_url')
  const handleDisconnectGitlab = makeDisconnectHandler(disconnectGitlab, 'GitLab')
  const handleConnectNotion = makeConnectHandler(connectNotion, 'authorization_url')
  const handleDisconnectNotion = makeDisconnectHandler(disconnectNotion, 'Notion')
  const handleConnectJira = makeConnectHandler(connectJira, 'authorization_url')
  const handleDisconnectJira = makeDisconnectHandler(disconnectJira, 'Jira')

  const [isResyncing, setIsResyncing] = useState(false)
  const [syncProgress, setSyncProgress] = useState<number | null>(null)
  const [syncTotal, setSyncTotal] = useState<number | null>(null)
  const cancelledRef = useRef(false)
  const isResyncingRef = useRef(false)

  const pollSyncProgress = useCallback(async () => {
    cancelledRef.current = false
    let settled = false
    for (let i = 0; i < 180; i++) {
      if (cancelledRef.current) return
      await new Promise((r) => setTimeout(r, 2000))
      if (cancelledRef.current) return
      try {
        const s = await getNotionSyncStatus()
        if (cancelledRef.current) return
        setSyncProgress(s.sync_progress ?? s.pages_count)
        setSyncTotal(s.sync_total ?? null)
        if (s.sync_status === 'error') {
          setError('Notion sync failed. You can try again.')
          settled = true
          break
        }
        if (s.sync_status !== 'syncing') {
          settled = true
          break
        }

        // Detect stale sync — if started_at is missing or older than 11 min
        const elapsed = s.sync_started_at
          ? Date.now() - new Date(s.sync_started_at).getTime()
          : Infinity
        if (elapsed > 11 * 60 * 1000) {
          setError('Notion sync appears stuck. Try re-syncing.')
          settled = true
          break
        }
      } catch {
        // Network error — keep polling, backend may recover
      }
    }
    if (cancelledRef.current) return
    if (!settled) {
      setError('Notion sync is taking too long. Try re-syncing.')
    }
    await fetchStatuses()
    setIsResyncing(false)
    setSyncProgress(null)
    setSyncTotal(null)
  }, [fetchStatuses])

  // Keep ref in sync with state for use in mount-only effect
  isResyncingRef.current = isResyncing

  // Resume Notion sync polling on mount if a sync is already in progress
  useEffect(() => {
    if (isLoading || isResyncingRef.current) return
    let cancelled = false
    getNotionSyncStatus()
      .then((s) => {
        if (cancelled) return
        if (s.sync_status === 'syncing') {
          // Check if sync is stale before resuming poll.
          // Missing sync_started_at = legacy sync, treat as stale.
          const elapsed = s.sync_started_at
            ? Date.now() - new Date(s.sync_started_at).getTime()
            : Infinity
          if (elapsed > 11 * 60 * 1000) {
            setError('Notion sync appears stuck. Try re-syncing.')
            return
          }
          setIsResyncing(true)
          setSyncProgress(s.sync_progress ?? 0)
          setSyncTotal(s.sync_total ?? null)
          pollSyncProgress()
        } else if (s.sync_status === 'error') {
          setError('Notion sync failed. You can try re-syncing.')
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
      cancelledRef.current = true
    }
    // isResyncing is read via ref to avoid re-triggering during sync.
    // pollSyncProgress and fetchStatuses are stable via useCallback.
  }, [isLoading, fetchStatuses, pollSyncProgress])

  const handleResyncNotion = async () => {
    setError(null)
    setIsResyncing(true)
    setSyncProgress(0)
    try {
      try {
        await resyncNotion()
      } catch (err) {
        // Backend returns 409 when resetting a stale sync — retry once
        if (err instanceof Error && err.message.includes('409')) {
          await new Promise((r) => setTimeout(r, 1000))
          await resyncNotion()
        } else {
          throw err
        }
      }
      await pollSyncProgress()
    } catch {
      setError('Failed to start Notion re-sync.')
      setIsResyncing(false)
      setSyncProgress(null)
      setSyncTotal(null)
    }
  }

  if (isLoading) {
    return (
      <div className="grid gap-3 md:grid-cols-2 items-start">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="rounded-2xl border border-border p-4 space-y-3">
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-5 rounded shrink-0" />
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-1.5 w-1.5 rounded-full ml-auto" />
            </div>
            <Skeleton className="h-8 w-20" />
          </div>
        ))}
      </div>
    )
  }

  const linear = statuses?.linear ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const slack = statuses?.slack ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const fathom = statuses?.fathom ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const github = statuses?.github ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const gitlab = statuses?.gitlab ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const notion = statuses?.notion ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const telegram = statuses?.telegram ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const jira = statuses?.jira ?? { status: 'disconnected' as const, external_name: null, connected_at: null }

  const connectedCount = [linear, slack, fathom, github, gitlab, notion, telegram, jira].filter(
    (s) => s.status === 'connected'
  ).length

  // Ticket provider mutual exclusion
  const linearDisabledReason = statuses ? ticketProviderDisabledReason('linear', statuses) : null
  const jiraDisabledReason = statuses ? ticketProviderDisabledReason('jira', statuses) : null

  return (
    <div className="space-y-4">
      {/* Status line */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Manage your tool connections
        </p>
        <span className="text-xs font-mono text-muted-foreground/60">
          {connectedCount}/8
        </span>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm animate-scale-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          <span className="flex-1 text-destructive">{error}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStatuses}
            className="h-7 gap-1.5 text-destructive hover:text-destructive"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* Cards grid */}
      <div className="grid gap-3 md:grid-cols-2 items-start">
        <div className="flex flex-col gap-3 stagger-children">
          <IntegrationCard
            name="Linear"
            icon={<LinearLogo width={20} height={20} className="text-violet-600 dark:text-violet-400" />}
            status={linear.status}
            externalName={linear.external_name}
            connectedAt={linear.connected_at}
            onConnect={handleConnectLinear}
            onDisconnect={handleDisconnectLinear}
            disabled={!!linearDisabledReason}
            disabledReason={linearDisabledReason ?? undefined}
          />
          <IntegrationCard
            name="Jira"
            icon={<JiraLogo width={20} height={20} />}
            status={jira.status}
            externalName={jira.external_name}
            connectedAt={jira.connected_at}
            onConnect={handleConnectJira}
            onDisconnect={handleDisconnectJira}
            disabled={!!jiraDisabledReason}
            disabledReason={jiraDisabledReason ?? undefined}
          />
          <IntegrationCard
            name="Fathom"
            icon={<FathomLogo width={20} height={20} />}
            status={fathom.status}
            externalName={fathom.external_name}
            connectedAt={fathom.connected_at}
            onConnect={() => {}}
            onDisconnect={handleDisconnectFathom}
            connectForm={<FathomConnect onConnected={fetchStatuses} />}
          />
          {/* Notion sync — compute derived state once via pure function */}
          {(() => {
            const ns = computeSyncState({ isResyncing, syncProgress, syncTotal })
            return (
              <IntegrationCard
                name="Notion"
                icon={<NotionLogo width={20} height={20} className="text-foreground" />}
                status={notion.status}
                externalName={displayName(notion.external_name)}
                connectedAt={notion.connected_at}
                onConnect={handleConnectNotion}
                onDisconnect={handleDisconnectNotion}
                syncing={ns.syncing}
                syncPercent={ns.percent}
                syncLabel={ns.label}
              >
                <div className="space-y-3">
                  {ns.syncing ? (
                    <>
                      {/* Phase label + counter */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
                          <span className="text-sm font-medium text-foreground">
                            {ns.phaseLabel}
                          </span>
                        </div>
                        {ns.hasTotal && (
                          <span className="text-xs font-mono text-muted-foreground">
                            {ns.progress}/{syncTotal}
                          </span>
                        )}
                      </div>

                      {/* Progress bar (only during phase 2 when we have a total) */}
                      {ns.percent != null && (
                        <div
                          className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
                          role="progressbar"
                          aria-valuenow={ns.percent}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label="Notion sync progress"
                        >
                          <div
                            className="h-full rounded-full bg-primary transition-all duration-700 ease-out relative overflow-hidden"
                            style={{ width: `${Math.max(ns.percent, 2)}%` }}
                          >
                            <div className="absolute inset-0 animate-[sync-shimmer_1.5s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/40 to-transparent" />
                          </div>
                        </div>
                      )}

                      {/* Reassurance */}
                      <p className="text-xs text-muted-foreground/70">
                        Syncing continues in the background — you can leave this page.
                      </p>
                    </>
                  ) : (
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-muted-foreground">
                        {notion.pages_synced != null && notion.pages_synced > 0
                          ? `${notion.pages_synced} pages synced${notion.last_sync_at ? ` \u00b7 ${formatRelativeTime(notion.last_sync_at)}` : ''}`
                          : 'No pages synced yet'}
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleResyncNotion}
                        className="text-[13px]"
                      >
                        Re-sync
                      </Button>
                    </div>
                  )}
                </div>
              </IntegrationCard>
            )
          })()}
        </div>

        <div className="flex flex-col gap-3 stagger-children">
          <IntegrationCard
            name="Slack"
            icon={<SlackLogo width={20} height={20} />}
            status={slack.status}
            externalName={slack.external_name}
            connectedAt={slack.connected_at}
            onConnect={handleConnectSlack}
            onDisconnect={handleDisconnectSlack}
          >
            <SlackChannels onSaved={fetchStatuses} />
          </IntegrationCard>
          <IntegrationCard
            name="Telegram"
            icon={<TelegramLogo width={20} height={20} className="text-[#26A5E4]" />}
            status={telegram.status}
            externalName={telegram.external_name}
            connectedAt={telegram.connected_at}
            onConnect={() => {}}
            onDisconnect={handleDisconnectTelegram}
            connectForm={<TelegramConnect onConnected={fetchStatuses} />}
          />
          <IntegrationCard
            name="GitHub"
            icon={<GitHubLogo width={20} height={20} className="text-foreground" />}
            status={github.status}
            externalName={github.external_name}
            connectedAt={github.connected_at}
            onConnect={handleConnectGithub}
            onDisconnect={handleDisconnectGithub}
          >
            <GithubRepos onSaved={fetchStatuses} />
          </IntegrationCard>
          <IntegrationCard
            name="GitLab"
            icon={<GitLabLogo width={20} height={20} className="text-foreground" />}
            status={gitlab.status}
            externalName={gitlab.external_name}
            connectedAt={gitlab.connected_at}
            onConnect={handleConnectGitlab}
            onDisconnect={handleDisconnectGitlab}
          />
        </div>
      </div>
    </div>
  )
}
