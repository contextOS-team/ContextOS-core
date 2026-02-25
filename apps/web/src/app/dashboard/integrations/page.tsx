'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Workflow, MessageSquare, Video, GitBranch } from 'lucide-react'
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
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(
    null
  )
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const searchParams = useSearchParams()

  // Handle GitHub OAuth callback query params
  useEffect(() => {
    const githubStatus = searchParams.get('github')
    if (githubStatus === 'connected') {
      const account = searchParams.get('account')
      setError(null)
      // Clean URL without reloading
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
      setError(
        err instanceof Error ? err.message : 'Failed to load integration status'
      )
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatuses()
  }, [fetchStatuses])

  // --- Linear handlers ---
  async function handleConnectLinear() {
    try {
      const { authorization_url } = await connectLinear()
      window.location.href = authorization_url
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to start Linear connection'
      )
    }
  }

  async function handleDisconnectLinear() {
    await disconnectLinear()
    await fetchStatuses()
  }

  // --- Slack handlers ---
  async function handleConnectSlack() {
    try {
      const { authorization_url } = await connectSlack()
      window.location.href = authorization_url
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to start Slack connection'
      )
    }
  }

  async function handleDisconnectSlack() {
    await disconnectSlack()
    await fetchStatuses()
  }

  // --- Fathom handlers ---
  async function handleDisconnectFathom() {
    await disconnectFathom()
    await fetchStatuses()
  }

  // --- GitHub handlers ---
  async function handleConnectGithub() {
    try {
      const { installation_url } = await connectGithub()
      window.location.href = installation_url
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to start GitHub connection'
      )
    }
  }

  async function handleDisconnectGithub() {
    await disconnectGithub()
    await fetchStatuses()
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Integrations</h2>
          <p className="text-muted-foreground text-sm mt-1">
            Connect your tools to enable context generation
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-48 animate-pulse rounded-xl border bg-muted/30"
            />
          ))}
        </div>
      </div>
    )
  }

  const linear = statuses?.linear ?? {
    status: 'disconnected' as const,
    external_name: null,
    connected_at: null,
  }
  const slack = statuses?.slack ?? {
    status: 'disconnected' as const,
    external_name: null,
    connected_at: null,
  }
  const fathom = statuses?.fathom ?? {
    status: 'disconnected' as const,
    external_name: null,
    connected_at: null,
  }
  const github = statuses?.github ?? {
    status: 'disconnected' as const,
    external_name: null,
    connected_at: null,
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Integrations</h2>
        <p className="text-muted-foreground text-sm mt-1">
          Connect your tools to enable context generation
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Integration cards grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Linear */}
        <IntegrationCard
          name="Linear"
          icon={<Workflow className="h-5 w-5 text-violet-600" />}
          description="Import issues and project context from Linear"
          status={linear.status}
          externalName={linear.external_name}
          connectedAt={linear.connected_at}
          onConnect={handleConnectLinear}
          onDisconnect={handleDisconnectLinear}
        />

        {/* Slack */}
        <IntegrationCard
          name="Slack"
          icon={<MessageSquare className="h-5 w-5 text-emerald-600" />}
          description="Monitor channels for relevant discussions and decisions"
          status={slack.status}
          externalName={slack.external_name}
          connectedAt={slack.connected_at}
          onConnect={handleConnectSlack}
          onDisconnect={handleDisconnectSlack}
        >
          <SlackChannels onSaved={fetchStatuses} />
        </IntegrationCard>

        {/* Fathom */}
        <IntegrationCard
          name="Fathom"
          icon={<Video className="h-5 w-5 text-blue-600" />}
          description="Ingest meeting transcripts for context enrichment"
          status={fathom.status}
          externalName={fathom.external_name}
          connectedAt={fathom.connected_at}
          onConnect={() => {
            /* Connect handled by FathomConnect form via connectForm prop */
          }}
          onDisconnect={handleDisconnectFathom}
          connectForm={<FathomConnect onConnected={fetchStatuses} />}
        />

        {/* GitHub */}
        <IntegrationCard
          name="GitHub"
          icon={<GitBranch className="h-5 w-5 text-gray-800" />}
          description="Import PRs, reviews, and code context from GitHub"
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
