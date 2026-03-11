'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Skeleton } from '@/components/ui/skeleton'
import { getIntegrationStatus, type IntegrationStatusResponse } from '@/lib/api'
import { IntegrationCards } from './integration-cards'

// ---------------------------------------------------------------------------
// Integrations Tab (orchestrator shell)
// ---------------------------------------------------------------------------

export function IntegrationsTab() {
  const searchParams = useSearchParams()
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Handle OAuth callback URL parameters
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

  return (
    <IntegrationCards
      statuses={statuses}
      isPageLoading={isLoading}
      error={error}
      fetchStatuses={fetchStatuses}
      setError={setError}
    />
  )
}
