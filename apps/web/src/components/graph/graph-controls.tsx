'use client'

import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Map,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { EntityType } from './types'
import { ENTITY_COLORS } from './constants'

interface GraphControlsProps {
  onZoomIn: () => void
  onZoomOut: () => void
  onFitView: () => void
  onToggleMiniMap: () => void
  showMiniMap: boolean
  entityCounts: Record<string, number>
  hiddenEntityTypes: Set<EntityType>
  onFilterChange: (hidden: Set<EntityType>) => void
}

const ALL_ENTITY_TYPES: EntityType[] = [
  'Ticket',
  'Person',
  'Decision',
  'PR',
  'Message',
  'Code',
  'CodeChunk',
  'SlackThread',
  'NotionPage',
  'Meeting',
]

export function GraphControls({
  onZoomIn,
  onZoomOut,
  onFitView,
  onToggleMiniMap,
  showMiniMap,
  entityCounts,
  hiddenEntityTypes,
  onFilterChange,
}: GraphControlsProps) {
  function toggleEntityType(type: EntityType) {
    const next = new Set(hiddenEntityTypes)
    if (next.has(type)) {
      next.delete(type)
    } else {
      next.add(type)
    }
    onFilterChange(next)
  }

  // Only show entity types that have nodes
  const visibleTypes = ALL_ENTITY_TYPES.filter((t) => (entityCounts[t] ?? 0) > 0)

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2">
      {/* Filter chips */}
      {visibleTypes.length > 0 && (
        <div className="flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--card)] px-2 py-1 backdrop-blur-sm">
          {visibleTypes.map((type) => {
            const isHidden = hiddenEntityTypes.has(type)
            const color = ENTITY_COLORS[type]
            const count = entityCounts[type] ?? 0
            return (
              <button
                key={type}
                onClick={() => toggleEntityType(type)}
                className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium transition-opacity hover:opacity-80"
                style={{
                  opacity: isHidden ? 0.35 : 1,
                  background: isHidden
                    ? 'transparent'
                    : `color-mix(in oklch, ${color} 12%, transparent)`,
                  color: isHidden ? 'var(--muted-foreground)' : color,
                }}
              >
                <span
                  className="rounded-full"
                  style={{
                    width: 6,
                    height: 6,
                    background: color,
                    opacity: isHidden ? 0.4 : 1,
                  }}
                />
                {type} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Control buttons */}
      <div className="flex items-center gap-0.5 rounded-full border border-[var(--border)] bg-[var(--card)] px-1.5 py-1 backdrop-blur-sm">
        <Button variant="ghost" size="icon-xs" onClick={onZoomIn} title="Zoom in">
          <ZoomIn />
        </Button>
        <Button variant="ghost" size="icon-xs" onClick={onZoomOut} title="Zoom out">
          <ZoomOut />
        </Button>
        <Button variant="ghost" size="icon-xs" onClick={onFitView} title="Fit view">
          <Maximize2 />
        </Button>
        <div className="mx-0.5 h-4 w-px bg-[var(--border)]" />
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={onToggleMiniMap}
          title={showMiniMap ? 'Hide minimap' : 'Show minimap'}
          style={{ opacity: showMiniMap ? 1 : 0.5 }}
        >
          <Map />
        </Button>
      </div>
    </div>
  )
}
