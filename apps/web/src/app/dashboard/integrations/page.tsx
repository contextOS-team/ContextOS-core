'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  FathomLogo,
} from '@/components/icons/brand-logos'
import {
  getIntegrationStatus,
  connectLinear,
  disconnectLinear,
  connectSlack,
  disconnectSlack,
  disconnectFathom,
  connectGithub,
  disconnectGithub,
  type IntegrationStatusResponse,
} from '@/lib/api'
import { IntegrationCard } from './integration-card'
import { SlackChannels } from './slack-channels'
import { FathomConnect } from './fathom-connect'
import { GithubRepos } from './github-repos'

export default function IntegrationsPage() {
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const searchParams = useSearchParams()

  useEffect(() => {
    const githubStatus = searchParams.get('github')
    if (githubStatus === 'connected') {
      setError(null)
      window.history.replaceState({}, '', '/dashboard/integrations')
    } else if (githubStatus === 'error') {
      const reason = searchParams.get('reason') || 'unknown'
      const messages: Record<string, string> = {
        invalid_state: 'GitHub connection failed: invalid or expired session. Please try again.',
        callback_failed: 'GitHub connection failed. Please try again.',
        internal_error: 'An internal error occurred during GitHub connection. Please try again.',
      }
      setError(messages[reason] || `GitHub connection failed: ${reason}`)
      window.history.replaceState({}, '', '/dashboard/integrations')
    }
  }, [searchParams])

  const fetchStatuses = useCallback(async () => {
    try {
      const data = await getIntegrationStatus()
      setStatuses(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load integration status')
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
        setError(err instanceof Error ? err.message : `Failed to start connection`)
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
  const handleConnectGithub = makeConnectHandler(connectGithub, 'installation_url')
  const handleDisconnectGithub = makeDisconnectHandler(disconnectGithub, 'GitHub')

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <div>
          <div className="h-8 w-48 animate-pulse rounded-lg bg-muted" />
          <div className="h-4 w-32 animate-pulse rounded-lg bg-muted mt-2" />
        </div>
        <div className="grid gap-3 md:grid-cols-2 stagger-children">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-44 animate-pulse rounded-2xl bg-muted" />
          ))}
        </div>
      </div>
    )
  }

  const linear = statuses?.linear ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const slack = statuses?.slack ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const fathom = statuses?.fathom ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const github = statuses?.github ?? { status: 'disconnected' as const, external_name: null, connected_at: null }

  const connectedCount = [linear, slack, fathom, github].filter((s) => s.status === 'connected').length

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.03em] text-foreground">Integrations</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your tool connections
          <span className="ml-2 text-xs font-mono text-muted-foreground/60">
            {connectedCount}/4
          </span>
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm animate-scale-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          <span className="flex-1 text-destructive">{error}</span>
          <Button variant="ghost" size="sm" onClick={fetchStatuses} className="h-7 gap-1.5 text-destructive hover:text-destructive">
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* Cards */}
      <div className="grid gap-3 md:grid-cols-2 stagger-children">
        <IntegrationCard
          name="Linear"
          icon={<LinearLogo width={20} height={20} className="text-violet-600 dark:text-violet-400" />}
          status={linear.status}
          externalName={linear.external_name}
          connectedAt={linear.connected_at}
          onConnect={handleConnectLinear}
          onDisconnect={handleDisconnectLinear}
        />

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
          name="Fathom"
          icon={<FathomLogo width={20} height={20} />}
          status={fathom.status}
          externalName={fathom.external_name}
          connectedAt={fathom.connected_at}
          onConnect={() => {}}
          onDisconnect={handleDisconnectFathom}
          connectForm={<FathomConnect onConnected={fetchStatuses} />}
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
      </div>
    </div>
  )
}
