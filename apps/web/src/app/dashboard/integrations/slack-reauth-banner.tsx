'use client'

import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { connectSlack } from '@/lib/api'

interface Props {
  /**
   * Optional callback fired right before the redirect happens. Useful for
   * parents that want to refetch status or close popovers.
   */
  onReconnectStarted?: () => void
}

/**
 * Amber banner shown inside the Slack integration card when the stored
 * OAuth install predates the user_scope change (Plan 39-01) or predates
 * the Phase 39.1 channel-scope expansion. Clicking "Reconnect Slack"
 * runs the standard connectSlack() OAuth flow.
 */
export function SlackReauthBanner({ onReconnectStarted }: Props) {
  const [busy, setBusy] = useState(false)

  async function handleReconnect() {
    setBusy(true)
    try {
      const { authorization_url } = await connectSlack()
      onReconnectStarted?.()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Failed to start Slack reconnect',
      )
      setBusy(false)
    }
  }

  return (
    <div
      className="flex items-start gap-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3"
      role="status"
      aria-live="polite"
    >
      <AlertTriangle
        className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
        aria-hidden="true"
      />
      <div className="flex-1 space-y-1.5">
        <p className="text-xs font-medium text-foreground">
          Reconnect required for channel + DM ingestion
        </p>
        <p
          className="text-xs text-muted-foreground"
          style={{ textWrap: 'pretty' }}
        >
          Your Slack connection needs additional scopes to read channels and
          DMs. Reconnect to grant access.
        </p>
        <Button
          size="xs"
          variant="outline"
          onClick={handleReconnect}
          disabled={busy}
          className="mt-1"
        >
          {busy ? 'Redirecting…' : 'Reconnect Slack'}
        </Button>
      </div>
    </div>
  )
}
