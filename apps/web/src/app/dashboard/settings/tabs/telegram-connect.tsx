'use client'

/**
 * TelegramConnect — Phase 40 shared-bot pairing wrapper.
 *
 * Thin shell around TelegramPairingProgress. Resolves the current workspace_id
 * client-side (required for the Realtime filter) and forwards onConnected to
 * the parent so it can refresh integration statuses when the bot's claim_chat
 * handler inserts the telegram_chat_workspace row.
 *
 * Workspace resolution mirrors the existing pattern in
 * apps/web/src/app/dashboard/page.tsx and apps/web/src/app/dashboard/activity/page.tsx
 * (auth.getUser → workspace_members.maybeSingle). RLS scopes the row to the
 * authenticated user, so a typed Supabase select is safe here.
 *
 * NOTE: This file used to host a bot-token paste form (Phase 26). Plan 40-02
 * replaces it with the deep-link flow; Plan 40-03 will delete the legacy
 * `connectTelegram(botToken)` API client this file used to call.
 */

import { useEffect, useState } from 'react'

import { createClient } from '@/lib/supabase/client'
import { TelegramPairingProgress } from '../../integrations/telegram-pairing-progress'

export function TelegramConnect({ onConnected }: { onConnected?: () => void }) {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      const supabase = createClient()
      const {
        data: { user },
      } = await supabase.auth.getUser()
      if (!user || cancelled) return
      const { data: ws, error: wsError } = await supabase
        .from('workspace_members')
        .select('workspace_id')
        .eq('user_id', user.id)
        .limit(1)
        .maybeSingle()
      if (cancelled) return
      if (wsError) {
        setError('Failed to load workspace. Reload and try again.')
        return
      }
      if (ws?.workspace_id) {
        setWorkspaceId(ws.workspace_id as string)
      } else {
        setError('No workspace found for this account.')
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return <p className="text-xs text-destructive">{error}</p>
  }

  if (!workspaceId) {
    return <p className="text-xs text-muted-foreground">Loading…</p>
  }

  return (
    <TelegramPairingProgress
      workspaceId={workspaceId}
      onConnected={() => onConnected?.()}
      onClose={onConnected}
    />
  )
}
