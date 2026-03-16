'use client'

import { useEffect, useRef, useCallback } from 'react'
import { ArrowRight, ExternalLink } from 'lucide-react'
import type { GraphNodeData, GraphEdgeData } from './types'
import { getEntityExternalUrl, HIDDEN_NODE_PROPERTIES } from './utils'
import { ENTITY_COLORS, ENTITY_ICONS } from './constants'
import type { Edge } from '@xyflow/react'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface NodePopoverProps {
  node: GraphNodeData
  position: { x: number; y: number }
  edges: Edge<GraphEdgeData>[]
  onClose: () => void
  onExpand: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NodePopover({
  node,
  position,
  edges,
  onClose,
  onExpand,
}: NodePopoverProps) {
  const ref = useRef<HTMLDivElement>(null)

  // Close on Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // Close on click outside
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as globalThis.Node)) {
        onClose()
      }
    }
    // Delay binding so the click that opened the popover doesn't close it
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleMouseDown)
    }, 0)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('mousedown', handleMouseDown)
    }
  }, [onClose])

  // Count connections
  const connectedCount = edges.filter(
    (e) => e.source === node.id || e.target === node.id
  ).length

  // Icon + color
  const Icon = ENTITY_ICONS[node.entityType]
  const color = ENTITY_COLORS[node.entityType]

  // Key properties (first 3), excluding internal metadata
  const propEntries = Object.entries(node.properties)
    .filter(([key]) => !HIDDEN_NODE_PROPERTIES.has(key))
    .slice(0, 3)

  const handleExpand = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onExpand()
    },
    [onExpand]
  )

  return (
    <div
      ref={ref}
      className="absolute z-50 animate-fade-in-up"
      style={{
        left: position.x,
        top: position.y,
        transform: 'translate(-50%, 8px)',
      }}
    >
      <div
        className="w-64 rounded-lg border shadow-lg p-3"
        style={{
          background: 'var(--card)',
          borderColor: 'var(--border)',
        }}
      >
        {/* Header: icon + name */}
        <div className="flex items-center gap-2 mb-2">
          <Icon className="h-4 w-4 shrink-0" style={{ color }} />
          <span className="text-sm font-semibold text-foreground truncate">
            {node.name}
          </span>
        </div>

        {/* Entity type badge */}
        <span
          className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium mb-2"
          style={{
            background: `color-mix(in oklch, ${color} 10%, transparent)`,
            color,
          }}
        >
          {node.entityType}
        </span>

        {/* Key properties */}
        {propEntries.length > 0 && (
          <div className="space-y-0.5 mb-2">
            {propEntries.map(([key, value]) => (
              <div key={key} className="flex items-baseline gap-1.5 text-xs">
                <span className="text-muted-foreground shrink-0">{key}:</span>
                <span className="text-foreground/80 truncate">
                  {String(value ?? '')}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Connection count */}
        <p className="text-xs text-muted-foreground mb-2">
          {connectedCount} connection{connectedCount !== 1 ? 's' : ''}
        </p>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleExpand}
            className="flex items-center gap-1 text-xs font-medium transition-colors hover:opacity-80"
            style={{ color: 'var(--primary)' }}
          >
            Expand
            <ArrowRight className="h-3 w-3" />
          </button>
          {(() => {
            const url = getEntityExternalUrl(node)
            return url ? (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                Open
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null
          })()}
        </div>
      </div>
    </div>
  )
}
