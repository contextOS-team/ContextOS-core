'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { createClient } from '@/lib/supabase/client'
import { displayName, formatRelativeTime } from '@/lib/utils'
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  FathomLogo,
  NotionLogo,
} from '@/components/icons/brand-logos'
import {
  getIntegrationStatus,
  connectLinear,
  connectSlack,
  connectGithub,
  connectNotion,
  type IntegrationStatusResponse,
} from '@/lib/api'

const INTEGRATIONS = [
  {
    key: 'linear' as const,
    name: 'Linear',
    logo: LinearLogo,
    brandColor: 'bg-violet-500',
    brandBorder: 'border-l-violet-500',
    logoClass: 'text-violet-600 dark:text-violet-400',
  },
  {
    key: 'slack' as const,
    name: 'Slack',
    logo: SlackLogo,
    brandColor: 'bg-emerald-500',
    brandBorder: 'border-l-emerald-500',
    logoClass: '', // Slack logo has its own multi-color fills
  },
  {
    key: 'fathom' as const,
    name: 'Fathom',
    logo: FathomLogo,
    brandColor: 'bg-cyan-500',
    brandBorder: 'border-l-cyan-500',
    logoClass: '', // Fathom logo has its own fill
  },
  {
    key: 'github' as const,
    name: 'GitHub',
    logo: GitHubLogo,
    brandColor: 'bg-foreground',
    brandBorder: 'border-l-foreground',
    logoClass: 'text-foreground dark:text-foreground',
  },
  {
    key: 'notion' as const,
    name: 'Notion',
    logo: NotionLogo,
    brandColor: 'bg-foreground',
    brandBorder: 'border-l-foreground',
    logoClass: 'text-foreground dark:text-foreground',
  },
]

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<{ email: string; fullName: string | null } | null>(null)
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setError(null)
    try {
      const [userRes, statusRes] = await Promise.all([
        createClient().auth.getUser(),
        getIntegrationStatus(),
      ])
      const u = userRes.data.user
      if (u) {
        setUser({
          email: u.email ?? '',
          fullName: u.user_metadata?.full_name ?? null,
        })
      }
      setStatuses(statusRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleQuickConnect = useCallback(
    async (key: (typeof INTEGRATIONS)[number]['key']) => {
      try {
        if (key === 'linear') {
          const { authorization_url } = await connectLinear()
          window.location.href = authorization_url
        } else if (key === 'slack') {
          const { authorization_url } = await connectSlack()
          window.location.href = authorization_url
        } else if (key === 'github') {
          const { installation_url } = await connectGithub()
          window.location.href = installation_url
        } else if (key === 'notion') {
          const { authorization_url } = await connectNotion()
          window.location.href = authorization_url
        } else {
          router.push('/dashboard/integrations')
        }
      } catch {
        router.push('/dashboard/integrations')
      }
    },
    [router]
  )

  const firstName = user
    ? user.fullName
      ? user.fullName.split(' ')[0]
      : user.email.split('@')[0]
    : ''

  const connectedCount = statuses
    ? INTEGRATIONS.filter((i) => statuses[i.key].status === 'connected').length
    : 0

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <div className="h-4 w-48 animate-pulse rounded bg-muted" />
        <div className="rounded-xl border bg-card p-1">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-[52px] animate-pulse rounded-lg bg-muted/50 mb-1 last:mb-0" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Subtle header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {getGreeting()}{firstName ? `, ${firstName}` : ''}
        </p>
        <span className="text-xs text-muted-foreground font-mono tabular-nums">
          {connectedCount}/5 connected
        </span>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm animate-scale-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          <span className="flex-1 text-destructive">{error}</span>
          <Button variant="ghost" size="sm" onClick={loadData} className="h-7 gap-1.5 text-destructive hover:text-destructive">
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* Integration status -- the hero section */}
      <div>
        <h3 className="text-[13px] font-medium text-muted-foreground uppercase tracking-[0.08em] mb-3">
          Integrations
        </h3>

        <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
          {INTEGRATIONS.map((integration) => {
            const status = statuses?.[integration.key]
            const Logo = integration.logo
            const isConnected = status?.status === 'connected'
            const isError = status?.status === 'error'
            const name = displayName(status?.external_name)

            return (
              <div
                key={integration.key}
                className={`flex items-center gap-4 px-4 py-3 transition-colors duration-150 hover:bg-muted/40 ${
                  isConnected ? `border-l-2 ${integration.brandBorder}` : 'border-l-2 border-l-transparent'
                } ${!isConnected ? 'opacity-60' : ''}`}
              >
                {/* Brand logo */}
                <div className="shrink-0">
                  <Logo width={18} height={18} className={integration.logoClass} />
                </div>

                {/* Name + external info */}
                <div className="flex-1 min-w-0 flex items-center gap-3">
                  <span className="text-sm font-medium text-foreground">{integration.name}</span>
                  {isConnected && name && (
                    <span className="text-xs text-muted-foreground truncate hidden sm:inline">{name}</span>
                  )}
                  {isConnected && status?.connected_at && (
                    <span className="text-[11px] text-muted-foreground/60 font-mono hidden md:inline">
                      {formatRelativeTime(status.connected_at)}
                    </span>
                  )}
                </div>

                {/* Status dot */}
                <span
                  className={`shrink-0 h-1.5 w-1.5 rounded-full ${
                    isConnected
                      ? 'bg-emerald-500'
                      : isError
                        ? 'bg-red-500'
                        : 'border border-muted-foreground/30'
                  }`}
                />

                {/* Action */}
                <div className="shrink-0 w-[72px] text-right">
                  {isConnected ? (
                    <button
                      onClick={() => router.push('/dashboard/integrations')}
                      className="text-xs text-muted-foreground hover:text-foreground transition-colors duration-150"
                    >
                      Manage
                    </button>
                  ) : isError ? (
                    <button
                      onClick={() => handleQuickConnect(integration.key)}
                      className="text-xs text-destructive hover:text-destructive/80 transition-colors duration-150"
                    >
                      Reconnect
                    </button>
                  ) : integration.key === 'fathom' ? (
                    <button
                      onClick={() => router.push('/dashboard/integrations')}
                      className="text-xs text-primary hover:text-primary/80 transition-colors duration-150"
                    >
                      Configure
                    </button>
                  ) : (
                    <button
                      onClick={() => handleQuickConnect(integration.key)}
                      className="text-xs text-primary hover:text-primary/80 transition-colors duration-150"
                    >
                      Connect
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
