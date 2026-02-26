'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Workflow,
  MessageSquare,
  Video,
  GitBranch,
  CheckCircle2,
  Circle,
  X,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { createClient } from '@/lib/supabase/client'
import { formatRelativeTime } from '@/lib/utils'
import {
  getIntegrationStatus,
  connectLinear,
  connectSlack,
  connectGithub,
  type IntegrationStatusResponse,
} from '@/lib/api'

const INTEGRATIONS = [
  { key: 'linear' as const, name: 'Linear', icon: Workflow, color: 'text-violet-600', bg: 'bg-violet-50' },
  { key: 'slack' as const, name: 'Slack', icon: MessageSquare, color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { key: 'fathom' as const, name: 'Fathom', icon: Video, color: 'text-blue-600', bg: 'bg-blue-50' },
  { key: 'github' as const, name: 'GitHub', icon: GitBranch, color: 'text-gray-800', bg: 'bg-gray-100' },
]

const SETUP_DISMISSED_KEY = 'contextos:setup-dismissed'

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

/** Hide raw UUIDs — show the name only if it looks human-readable */
function displayName(name: string | null | undefined): string | null {
  if (!name) return null
  if (/^[0-9a-f]{8}-/i.test(name)) return null
  return name
}

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<{ email: string; fullName: string | null } | null>(null)
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showSetup, setShowSetup] = useState(() => {
    if (typeof window === 'undefined') return true
    return localStorage.getItem(SETUP_DISMISSED_KEY) !== 'true'
  })

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

  function handleDismissSetup() {
    setShowSetup(false)
    localStorage.setItem(SETUP_DISMISSED_KEY, 'true')
  }

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

  const allConnected = connectedCount === 4
  const circumference = 2 * Math.PI * 18
  const progressOffset = circumference * (1 - connectedCount / 4)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <div className="h-9 w-72 animate-pulse rounded-md bg-muted" />
          <div className="h-5 w-56 animate-pulse rounded-md bg-muted" />
        </div>
        <div className="h-20 animate-pulse rounded-xl border bg-muted" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">
          {getGreeting()}{firstName ? `, ${firstName}` : ''}
        </h2>
        <p className="text-muted-foreground">
          Here&apos;s your workspace at a glance
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <Button variant="ghost" size="sm" onClick={loadData} className="h-7 gap-1.5 text-destructive hover:text-destructive">
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* Setup Progress — compact inline banner, dismissible, persisted */}
      {showSetup && (
        <Card className={allConnected ? 'border-emerald-200 bg-emerald-50/30' : ''}>
          <CardContent className="flex items-center gap-4 py-4">
            {/* Mini progress ring */}
            <svg width={48} height={48} viewBox="0 0 48 48" className="shrink-0" role="img" aria-label={`${connectedCount} of 4 integrations connected`}>
              <circle cx={24} cy={24} r={18} fill="none" stroke="#e4e4e7" strokeWidth={4} />
              <circle
                cx={24} cy={24} r={18} fill="none"
                stroke={allConnected ? '#10b981' : '#4f46e5'}
                strokeWidth={4}
                strokeDasharray={circumference}
                strokeDashoffset={progressOffset}
                strokeLinecap="round"
                transform="rotate(-90 24 24)"
              />
              <text
                x={24} y={24}
                textAnchor="middle"
                dominantBaseline="central"
                style={{ fontSize: 11, fontWeight: 700 }}
                className="fill-foreground"
              >
                {connectedCount}/4
              </text>
            </svg>

            {/* Inline checklist */}
            <div className="flex flex-1 flex-wrap items-center gap-x-5 gap-y-1">
              {INTEGRATIONS.map((integration) => {
                const connected = statuses?.[integration.key].status === 'connected'
                return (
                  <span key={integration.key} className="flex items-center gap-1.5 text-sm">
                    {connected ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <Circle className="h-4 w-4 text-gray-300" />
                    )}
                    <span className={connected ? 'text-muted-foreground' : 'text-foreground'}>
                      {integration.name}
                    </span>
                    {!connected && (
                      <button
                        onClick={() => handleQuickConnect(integration.key)}
                        className="ml-0.5 text-xs font-medium text-primary hover:underline"
                      >
                        Connect
                      </button>
                    )}
                  </span>
                )
              })}
            </div>

            {/* Dismiss */}
            <button
              onClick={handleDismissSetup}
              className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              aria-label="Dismiss setup progress"
            >
              <X className="h-4 w-4" />
            </button>
          </CardContent>
        </Card>
      )}

      {/* Integration Status Grid */}
      <div>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Integrations</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {INTEGRATIONS.map((integration) => {
            const status = statuses?.[integration.key]
            const Icon = integration.icon
            const isConnected = status?.status === 'connected'
            const isError = status?.status === 'error'
            const name = displayName(status?.external_name)

            return (
              <Card
                key={integration.key}
                className="cursor-pointer transition-all hover:shadow-md hover:border-primary/20"
                onClick={() => router.push('/dashboard/integrations')}
              >
                <CardContent className="flex items-start gap-3 p-4">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${integration.bg}`}>
                    <Icon className={`h-4 w-4 ${integration.color}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium">{integration.name}</span>
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                          isConnected ? 'bg-emerald-500' : isError ? 'bg-red-500' : 'bg-gray-300'
                        }`}
                      />
                    </div>
                    {isConnected ? (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {name && <span className="font-medium text-foreground">{name}</span>}
                        {name && status?.connected_at && ' · '}
                        {status?.connected_at
                          ? `Connected ${formatRelativeTime(status.connected_at)}`
                          : 'Connected'}
                      </p>
                    ) : (
                      <p className="mt-0.5 text-xs text-muted-foreground">Not connected</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
