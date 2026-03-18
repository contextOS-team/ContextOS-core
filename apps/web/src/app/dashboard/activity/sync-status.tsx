'use client'

import { INTEGRATION_COLORS } from './types'
import { formatTimelineTimestamp } from './formatters'

interface SyncStatusProps {
  syncStatuses: Array<{ integration: string; lastSyncedAt: string }>
}

export function SyncStatus({ syncStatuses }: SyncStatusProps) {
  if (syncStatuses.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-4 pb-5 mb-1">
      {syncStatuses.map(({ integration, lastSyncedAt }) => {
        const color = INTEGRATION_COLORS[integration]
        return (
          <div
            key={integration}
            className="flex items-center gap-2 text-xs text-muted-foreground group"
          >
            <span
              className="inline-block h-1.5 w-1.5 rounded-full shrink-0 ring-2 ring-background"
              style={{ backgroundColor: color ?? 'currentColor' }}
            />
            <span className="capitalize font-medium text-foreground/60 group-hover:text-foreground/80 transition-colors">
              {integration}
            </span>
            <span className="text-muted-foreground/50 font-mono text-[11px]">
              {formatTimelineTimestamp(lastSyncedAt)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
