'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { syncTelegramHistory, getTelegramSyncStatus } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'

export function TelegramSyncSection() {
  const [isSyncing, setIsSyncing] = useState(false)
  const [messagesSynced, setMessagesSynced] = useState<number>(0)
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  const pollStatus = useCallback(async () => {
    try {
      const status = await getTelegramSyncStatus()
      setMessagesSynced(status.records_synced)
      setLastSyncAt(status.last_sync_at)
      if (status.sync_status === 'complete' || status.sync_status === 'idle') {
        setIsSyncing(false)
      } else if (status.sync_status === 'error') {
        setIsSyncing(false)
        setError(status.error_message || 'Sync failed')
      }
    } catch {
      // Non-blocking
    }
  }, [])

  // Load initial status and resume polling if sync in progress
  useEffect(() => {
    getTelegramSyncStatus()
      .then((status) => {
        setMessagesSynced(status.records_synced)
        setLastSyncAt(status.last_sync_at)
        if (status.sync_status === 'syncing') {
          setIsSyncing(true)
        }
      })
      .catch(() => {})
  }, [])

  // Poll while syncing
  useEffect(() => {
    if (!isSyncing) return
    pollRef.current = setInterval(pollStatus, 3000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [isSyncing, pollStatus])

  async function handleSync() {
    setError(null)
    setIsSyncing(true)
    try {
      await syncTelegramHistory()
    } catch (err) {
      if (err instanceof Error && err.message.includes('already in progress')) {
        // Already syncing — just poll
      } else {
        setError(err instanceof Error ? err.message : 'Failed to start sync')
        setIsSyncing(false)
      }
    }
  }

  if (isSyncing) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
          <span className="text-sm font-medium text-foreground">
            Syncing message history...
          </span>
          {messagesSynced > 0 && (
            <span className="text-xs font-mono text-muted-foreground">
              {messagesSynced} messages
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground/70">
          Syncing continues in the background -- you can leave this page.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {messagesSynced > 0
            ? `${messagesSynced} messages synced${lastSyncAt ? ` \u00b7 ${formatRelativeTime(lastSyncAt)}` : ''}`
            : 'No messages synced yet'}
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSync}
          className="text-[13px]"
        >
          {messagesSynced > 0 ? 'Re-sync' : 'Sync History'}
        </Button>
      </div>
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  )
}
