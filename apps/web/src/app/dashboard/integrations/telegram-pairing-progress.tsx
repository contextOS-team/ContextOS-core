'use client'

/**
 * TelegramPairingProgress — Phase 40 shared-bot pairing UI.
 *
 * Lifecycle:
 *   idle -> minting -> waiting -> (connected | expired)
 *
 *   - On mount we auto-trigger the flow (the parent IntegrationCard only
 *     renders this when the user clicks Connect, so mounting === user intent).
 *   - 'minting' shows a spinner while POST /api/telegram/pairing-code resolves.
 *   - 'waiting' shows the deep link, a 15-min countdown, and Cancel/Regenerate.
 *     A Supabase Realtime channel listens for INSERTs on telegram_chat_workspace
 *     filtered by workspace_id=eq.${workspaceId} (defense-in-depth even with RLS).
 *   - 'connected' renders briefly while the parent refreshes statuses.
 *   - 'expired' offers Regenerate + Cancel after the countdown reaches 0.
 *
 * Cleanup uses supabase.removeChannel(channel) per the project pattern (see
 * use-context-pages-realtime.ts) — required to avoid "TooManyChannels" under
 * React StrictMode double-invoke.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  ExternalLink,
  Loader2,
  RefreshCw,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js'

import { Button } from '@/components/ui/button'
import { createClient } from '@/lib/supabase/client'
import { createTelegramPairingCode } from '@/lib/api'

type Phase = 'idle' | 'minting' | 'waiting' | 'expired' | 'connected'

interface TelegramPairingProgressProps {
  /** Current authenticated user's workspace UUID — used for the Realtime filter. */
  workspaceId: string
  /** Called when a telegram_chat_workspace INSERT for this workspace is observed. */
  onConnected?: (chat: { chat_id: number; chat_title: string | null }) => void
  /** Called on Cancel / after a successful claim — parent should refresh statuses. */
  onClose?: () => void
}

export function TelegramPairingProgress({
  workspaceId,
  onConnected,
  onClose,
}: TelegramPairingProgressProps) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<Date | null>(null)
  const [secondsLeft, setSecondsLeft] = useState<number>(0)

  // Use a ref for onConnected so the Realtime effect can subscribe once per
  // (phase, workspaceId) pair without re-subscribing on parent re-renders.
  const onConnectedRef = useRef(onConnected)
  onConnectedRef.current = onConnected

  // Mint a new pairing code (also invoked by Regenerate).
  const startPairing = useCallback(async () => {
    setPhase('minting')
    try {
      const result = await createTelegramPairingCode()
      setDeepLink(result.deep_link)
      setExpiresAt(new Date(result.expires_at))
      setPhase('waiting')
      // Open the deep link in a new tab so the user lands in the Telegram app/web.
      window.open(result.deep_link, '_blank', 'noopener,noreferrer')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start pairing')
      setPhase('idle')
    }
  }, [])

  // Auto-start the flow when the component mounts. IntegrationCard only renders
  // the connectForm after the user clicks Connect, so mounting === user intent.
  // We intentionally run this exactly once.
  useEffect(() => {
    if (phase === 'idle') {
      void startPairing()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Countdown ticker — updates secondsLeft once per second; flips to 'expired' at 0.
  useEffect(() => {
    if (phase !== 'waiting' || !expiresAt) return

    const tick = () => {
      const remaining = Math.max(
        0,
        Math.floor((expiresAt.getTime() - Date.now()) / 1000),
      )
      setSecondsLeft(remaining)
      if (remaining === 0) {
        setPhase('expired')
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [phase, expiresAt])

  // Realtime subscription on telegram_chat_workspace INSERT for this workspace.
  // Filter is defense-in-depth — RLS already restricts rows to the user's
  // workspace, but the explicit filter avoids unnecessary payload routing.
  useEffect(() => {
    if (phase !== 'waiting' || !workspaceId) return

    const supabase = createClient()
    const channel = supabase
      .channel(`telegram-pairing-${workspaceId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'telegram_chat_workspace',
          filter: `workspace_id=eq.${workspaceId}`,
        },
        (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => {
          const row = payload.new as {
            chat_id?: number
            chat_title?: string | null
          }
          if (typeof row.chat_id === 'number') {
            setPhase('connected')
            onConnectedRef.current?.({
              chat_id: row.chat_id,
              chat_title: row.chat_title ?? null,
            })
          }
        },
      )
      .subscribe()

    return () => {
      // CRITICAL — required to avoid "TooManyChannels" under StrictMode.
      void supabase.removeChannel(channel)
    }
  }, [phase, workspaceId])

  function handleCancel() {
    setPhase('idle')
    onClose?.()
  }

  async function handleRegenerate() {
    await startPairing()
  }

  // RENDER ---------------------------------------------------------------

  if (phase === 'minting') {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Generating pairing link…
      </div>
    )
  }

  if (phase === 'connected') {
    return (
      <div className="flex items-center gap-2 text-xs text-emerald-500">
        <Check className="h-3.5 w-3.5" />
        Connected — refreshing…
      </div>
    )
  }

  if (phase === 'expired') {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-amber-500">
          <AlertTriangle className="h-3.5 w-3.5" />
          This pairing link expired.
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={handleRegenerate}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Regenerate
          </Button>
          <Button size="sm" variant="ghost" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  // phase === 'waiting' (also covers the brief 'idle' window before the
  // mount effect fires — we render the same shell so the layout doesn't jump).
  const minutes = Math.floor(secondsLeft / 60)
  const seconds = secondsLeft % 60
  const countdown = `${minutes}:${seconds.toString().padStart(2, '0')}`

  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? 'ContextOSBot'

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Waiting for @{botUsername} to join a Telegram group… (Choose a group when
        the Telegram app opens; the bot will post a confirmation in-chat.)
      </p>
      {deepLink && (
        <a
          href={deepLink}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Reopen Telegram link
        </a>
      )}
      <div className="flex items-center gap-2">
        <Button size="sm" variant="ghost" onClick={handleCancel}>
          <X className="mr-1.5 h-3.5 w-3.5" />
          Cancel
        </Button>
        <Button size="sm" variant="outline" onClick={handleRegenerate}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Regenerate
        </Button>
        <span className="ml-auto font-mono text-[11px] text-muted-foreground/70">
          {countdown}
        </span>
      </div>
    </div>
  )
}
