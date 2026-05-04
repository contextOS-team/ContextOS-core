'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  connectLinear,
  disconnectLinear,
  connectSlack,
  disconnectSlack,
  disconnectFathom,
  connectGithub,
  disconnectGithub,
  connectGitlab,
  disconnectGitlab,
  connectNotion,
  disconnectNotion,
  connectJira,
  disconnectJira,
  getSlackStatus,
  type IntegrationStatusResponse,
} from '@/lib/api'
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  GitLabLogo,
  FathomLogo,
  TelegramLogo,
  JiraLogo,
} from '@/components/icons/brand-logos'
import { IntegrationCard } from '../../integrations/integration-card'
import { ticketProviderDisabledReason } from '@/lib/ticket-provider'
import { SlackChannels } from '../../integrations/slack-channels'
import { SlackDmToggle } from '../../integrations/slack-dm-toggle'
import { SlackReauthBanner } from '../../integrations/slack-reauth-banner'
import { FathomConnect } from '../../integrations/fathom-connect'
import { GithubRepos } from '../../integrations/github-repos'
import { GitlabRepos } from '../../integrations/gitlab-repos'
import { TelegramConnect } from './telegram-connect'
import { NotionSyncSection } from './notion-sync-section'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConnectHandler(
  connectFn: () => Promise<{ authorization_url?: string; installation_url?: string }>,
  urlKey: 'authorization_url' | 'installation_url',
  setError: (error: string | null) => void
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

function makeDisconnectHandler(
  disconnectFn: () => Promise<unknown>,
  name: string,
  setError: (error: string | null) => void,
  fetchStatuses: () => Promise<void>
) {
  return async () => {
    try {
      await disconnectFn()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to disconnect ${name}`)
    }
    await fetchStatuses()
  }
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface IntegrationCardsProps {
  statuses: IntegrationStatusResponse | null
  isPageLoading: boolean
  error: string | null
  fetchStatuses: () => Promise<void>
  setError: (error: string | null) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function IntegrationCards({
  statuses,
  isPageLoading,
  error,
  fetchStatuses,
  setError,
}: IntegrationCardsProps) {
  const handleConnectLinear = makeConnectHandler(connectLinear, 'authorization_url', setError)
  const handleDisconnectLinear = makeDisconnectHandler(disconnectLinear, 'Linear', setError, fetchStatuses)
  const handleConnectSlack = makeConnectHandler(connectSlack, 'authorization_url', setError)
  const handleDisconnectSlack = makeDisconnectHandler(disconnectSlack, 'Slack', setError, fetchStatuses)
  const handleDisconnectFathom = makeDisconnectHandler(disconnectFathom, 'Fathom', setError, fetchStatuses)
  // Phase 40 shared-bot model: there is no workspace-level disconnect endpoint.
  // The user removes @ContextOSBot from each Telegram group; the bot's
  // my_chat_member handler then soft-deletes the chat→workspace mapping.
  const handleDisconnectTelegram = async () => {
    toast.info('To disconnect, remove @ContextOSBot from the Telegram group(s).')
  }
  const handleConnectGithub = makeConnectHandler(connectGithub, 'installation_url', setError)
  const handleDisconnectGithub = makeDisconnectHandler(disconnectGithub, 'GitHub', setError, fetchStatuses)
  const handleConnectGitlab = makeConnectHandler(connectGitlab, 'authorization_url', setError)
  const handleDisconnectGitlab = makeDisconnectHandler(disconnectGitlab, 'GitLab', setError, fetchStatuses)
  const handleConnectNotion = makeConnectHandler(connectNotion, 'authorization_url', setError)
  const handleDisconnectNotion = makeDisconnectHandler(disconnectNotion, 'Notion', setError, fetchStatuses)
  const handleConnectJira = makeConnectHandler(connectJira, 'authorization_url', setError)
  const handleDisconnectJira = makeDisconnectHandler(disconnectJira, 'Jira', setError, fetchStatuses)

  const linear = statuses?.linear ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const slack = statuses?.slack ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const fathom = statuses?.fathom ?? { status: 'disconnected' as const, external_name: null, connected_at: null }

  // Plan 39-03: fetch DM-toggle and needs_reauth flags from /api/slack/status.
  // The aggregator /api/integrations/status does not populate these fields.
  const [slackExtra, setSlackExtra] = useState<{
    needs_reauth: boolean
    include_dms: boolean
  } | null>(null)

  useEffect(() => {
    if (slack.status !== 'connected') {
      setSlackExtra(null)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const s = await getSlackStatus()
        if (!cancelled) {
          setSlackExtra({
            needs_reauth: s.needs_reauth,
            include_dms: s.include_dms,
          })
        }
      } catch {
        // Non-blocking: fall back to channel-picker-only UI on failure.
      }
    })()
    return () => {
      cancelled = true
    }
    // fetchStatuses is a prop from the parent and is NOT wrapped in
    // useCallback there. Including it in deps would cause an infinite
    // render loop (new reference each parent render). This effect only
    // depends on slack.status changing — which already triggers a refetch.
  }, [slack.status])

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
          <NotionSyncSection
            notionStatus={notion}
            isPageLoading={isPageLoading}
            fetchStatuses={fetchStatuses}
            onConnect={handleConnectNotion}
            onDisconnect={handleDisconnectNotion}
            setError={setError}
          />
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
            <div className="space-y-3">
              {slackExtra?.needs_reauth && (
                <SlackReauthBanner onReconnectStarted={fetchStatuses} />
              )}
              {slack.status === 'connected' && !slackExtra?.needs_reauth && (
                <SlackDmToggle initialIncludeDms={slackExtra?.include_dms} />
              )}
              <SlackChannels onSaved={fetchStatuses} />
            </div>
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
          >
            <GitlabRepos onSaved={fetchStatuses} />
          </IntegrationCard>
        </div>
      </div>
    </div>
  )
}
