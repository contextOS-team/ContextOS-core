'use client'

import { INTEGRATION_COLORS } from './types'
import { formatTimelineTimestamp } from './formatters'

interface SyncStatusProps {
  syncStatuses: Array<{ integration: string; lastSyncedAt: string }>
}

export function SyncStatus({ syncStatuses }: SyncStatusProps) {
  if (syncStatuses.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-3 pb-4 mb-2 border-b border-border">
      {syncStatuses.map(({ integration, lastSyncedAt }) => {
        const color = INTEGRATION_COLORS[integration]
        return (
          <div
            key={integration}
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span
              className="inline-block h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: color ?? 'currentColor' }}
            />
            <span className="capitalize">{integration}</span>
            <span className="text-muted-foreground/60">
              Last synced {formatTimelineTimestamp(lastSyncedAt)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
