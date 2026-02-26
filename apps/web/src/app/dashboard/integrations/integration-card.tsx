'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'
import { formatRelativeTime } from '@/lib/utils'

type IntegrationStatus = 'connected' | 'disconnected' | 'error'

interface IntegrationCardProps {
  name: string
  icon: React.ReactNode
  description: string
  status: IntegrationStatus
  externalName?: string | null
  connectedAt?: string | null
  onConnect: () => void | Promise<void>
  onDisconnect: () => void | Promise<void>
  /** Content shown in expandable section when connected (e.g. Slack channel picker). */
  children?: React.ReactNode
  /** Form shown inline when clicking Connect instead of redirecting (e.g. Fathom API key form). */
  connectForm?: React.ReactNode
  /** Custom background class for the icon container. */
  iconBgClass?: string
}

function StatusBadge({ status }: { status: IntegrationStatus }) {
  const styles: Record<IntegrationStatus, string> = {
    connected: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    disconnected: 'bg-gray-50 text-gray-500 border-gray-200',
    error: 'bg-red-50 text-red-700 border-red-200',
  }

  const labels: Record<IntegrationStatus, string> = {
    connected: 'Connected',
    disconnected: 'Not connected',
    error: 'Error',
  }

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      {status === 'connected' && (
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500" />
      )}
      {status === 'error' && (
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-red-500" />
      )}
      {labels[status]}
    </span>
  )
}

export function IntegrationCard({
  name,
  icon,
  description,
  status,
  externalName,
  connectedAt,
  onConnect,
  onDisconnect,
  children,
  connectForm,
  iconBgClass,
}: IntegrationCardProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showConnectForm, setShowConnectForm] = useState(false)

  async function handleConnect() {
    // If a connectForm is provided, show it inline instead of calling onConnect
    if (connectForm) {
      setShowConnectForm(true)
      return
    }

    setIsLoading(true)
    try {
      await onConnect()
    } finally {
      setIsLoading(false)
    }
  }

  async function handleDisconnect() {
    const confirmed = window.confirm(
      `Disconnect ${name}?\n\nThis will stop syncing data. Existing data is kept.`
    )
    if (!confirmed) return

    setIsLoading(true)
    try {
      await onDisconnect()
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className="gap-0 py-0 overflow-hidden transition-shadow hover:shadow-md hover:border-primary/20">
      <div className="flex flex-row items-start justify-between gap-4 px-7 pt-7 pb-4">
        <div className="flex items-start gap-3">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${iconBgClass ?? 'bg-muted/50'}`}>
            {icon}
          </div>
          <div className="space-y-1">
            <CardTitle className="text-lg">{name}</CardTitle>
            <CardDescription className="text-sm leading-relaxed">
              {description}
            </CardDescription>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      <CardContent className="px-7 pb-6 pt-0">
        {/* Connection info */}
        {status === 'connected' && (externalName || connectedAt) && (
          <div className="mb-4">
            {externalName && (
              <p className="text-sm font-medium text-foreground">
                {/^[0-9a-f]{8}-/i.test(externalName) ? 'Connected' : externalName}
              </p>
            )}
            {connectedAt && (
              <p className="text-xs text-muted-foreground">
                Connected {formatRelativeTime(connectedAt)}
              </p>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {status === 'connected' ? (
            <>
              {children && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsExpanded(!isExpanded)}
                >
                  {isExpanded ? 'Hide settings' : 'Settings'}
                </Button>
              )}
              <button
                onClick={handleDisconnect}
                disabled={isLoading}
                className="text-xs text-muted-foreground hover:text-red-600 transition-colors disabled:opacity-50"
              >
                {isLoading ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </>
          ) : (
            !showConnectForm && (
              <Button
                size="sm"
                onClick={handleConnect}
                disabled={isLoading}
              >
                {isLoading ? 'Connecting...' : 'Connect'}
              </Button>
            )
          )}
        </div>

        {/* Inline connect form (e.g. Fathom API key) */}
        {connectForm && status !== 'connected' && showConnectForm && (
          <div className="mt-4 rounded-lg border bg-muted/30 p-4">
            {connectForm}
          </div>
        )}
      </CardContent>

      {/* Expandable content (channel picker, etc.) */}
      {children && status === 'connected' && isExpanded && (
        <div className="border-t bg-muted/30 px-7 py-5">{children}</div>
      )}
    </Card>
  )
}
