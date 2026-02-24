'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'

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

function formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHours = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) return `${diffDays}d ago`
  if (diffHours > 0) return `${diffHours}h ago`
  if (diffMin > 0) return `${diffMin}m ago`
  return 'just now'
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
    <Card className="gap-0 py-0 overflow-hidden transition-shadow hover:shadow-md">
      <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 px-6 pt-6 pb-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border bg-muted/50">
            {icon}
          </div>
          <div className="space-y-1">
            <CardTitle className="text-base">{name}</CardTitle>
            <CardDescription className="text-xs leading-relaxed">
              {description}
            </CardDescription>
          </div>
        </div>
        <StatusBadge status={status} />
      </CardHeader>

      <CardContent className="px-6 pb-5 pt-0">
        {/* Connection info */}
        {status === 'connected' && (externalName || connectedAt) && (
          <p className="mb-4 text-xs text-muted-foreground">
            {externalName && (
              <span className="font-medium text-foreground">
                {externalName}
              </span>
            )}
            {externalName && connectedAt && ' \u00b7 '}
            {connectedAt && <>Connected {formatRelativeTime(connectedAt)}</>}
          </p>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {status === 'connected' ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
                disabled={isLoading}
                className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
              >
                {isLoading ? 'Disconnecting...' : 'Disconnect'}
              </Button>
              {children && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="text-muted-foreground"
                >
                  {isExpanded ? 'Hide settings' : 'Settings'}
                </Button>
              )}
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
        <div className="border-t bg-muted/30 px-6 py-5">{children}</div>
      )}
    </Card>
  )
}
