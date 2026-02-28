'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { displayName, formatRelativeTime } from '@/lib/utils'
import { ChevronDown, Loader2 } from 'lucide-react'

type IntegrationStatus = 'connected' | 'disconnected' | 'error'

interface IntegrationCardProps {
  name: string
  icon: React.ReactNode
  status: IntegrationStatus
  externalName?: string | null
  connectedAt?: string | null
  onConnect: () => void | Promise<void>
  onDisconnect: () => void | Promise<void>
  children?: React.ReactNode
  connectForm?: React.ReactNode
}

function StatusIndicator({ status }: { status: IntegrationStatus }) {
  if (status === 'connected') {
    return (
      <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-emerald-500" />
    )
  }
  if (status === 'error') {
    return (
      <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-red-500" />
    )
  }
  return (
    <span className="shrink-0 h-1.5 w-1.5 rounded-full border border-muted-foreground/30" />
  )
}

export function IntegrationCard({
  name,
  icon,
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

  const displayedName = displayName(externalName)

  return (
    <Card className="gap-0 py-0 overflow-hidden transition-shadow duration-200 hover:shadow-lg hover:shadow-black/[0.03] dark:hover:shadow-black/20 group">
      <div className="flex flex-row items-center justify-between gap-3 px-5 pt-5 pb-2">
        <div className="flex items-center gap-3 min-w-0">
          <div className="shrink-0">
            {icon}
          </div>
          <div className="flex items-center gap-2 min-w-0">
            <h3 className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">{name}</h3>
            <StatusIndicator status={status} />
          </div>
        </div>
        {/* Connection info inline with header */}
        {status === 'connected' && (displayedName || connectedAt) && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
            {displayedName && (
              <span className="font-medium text-foreground/70 truncate max-w-[120px]">
                {displayedName}
              </span>
            )}
            {connectedAt && (
              <span className="font-mono text-[11px] text-muted-foreground/60">
                {formatRelativeTime(connectedAt)}
              </span>
            )}
          </div>
        )}
      </div>

      <CardContent className="px-5 pb-4 pt-0">
        {/* Actions */}
        <div className="flex items-center gap-2 h-8">
          {status === 'connected' ? (
            <>
              {children && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="gap-1.5 text-[13px]"
                >
                  {isExpanded ? 'Hide settings' : 'Settings'}
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                </Button>
              )}
              <button
                onClick={handleDisconnect}
                disabled={isLoading}
                className="text-[12px] text-muted-foreground hover:text-red-500 dark:hover:text-red-400 transition-colors duration-150 disabled:opacity-50 ml-1"
              >
                {isLoading ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Disconnecting
                  </span>
                ) : 'Disconnect'}
              </button>
            </>
          ) : (
            !showConnectForm && (
              <Button
                size="sm"
                onClick={handleConnect}
                disabled={isLoading}
                className="text-[13px]"
              >
                {isLoading ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Connecting
                  </span>
                ) : 'Connect'}
              </Button>
            )
          )}
        </div>

        {/* Inline connect form */}
        {connectForm && status !== 'connected' && showConnectForm && (
          <div className="mt-4 rounded-xl border bg-muted/30 p-4">
            {connectForm}
          </div>
        )}
      </CardContent>

      {/* Expandable content */}
      {children && status === 'connected' && isExpanded && (
        <div className="border-t bg-muted/20 px-5 py-5">{children}</div>
      )}
    </Card>
  )
}
