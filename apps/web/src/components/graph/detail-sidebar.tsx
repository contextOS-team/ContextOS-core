'use client'

import { useEffect, useCallback } from 'react'
import { X, ArrowRight, ArrowLeft } from 'lucide-react'
import type { GraphNodeData } from './types'
import { ENTITY_COLORS, ENTITY_ICONS } from './constants'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ConnectionInfo {
  node: GraphNodeData
  edgeType: string
  direction: 'incoming' | 'outgoing'
}

export interface DetailSidebarProps {
  node: GraphNodeData
  connections: ConnectionInfo[]
  onClose: () => void
  onNavigateToNode: (nodeId: string) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DetailSidebar({
  node,
  connections,
  onClose,
  onNavigateToNode,
}: DetailSidebarProps) {
  // Close on Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const Icon = ENTITY_ICONS[node.entityType]
  const color = ENTITY_COLORS[node.entityType]
  const propEntries = Object.entries(node.properties)

  const handleConnectionClick = useCallback(
    (nodeId: string) => {
      onNavigateToNode(nodeId)
    },
    [onNavigateToNode]
  )

  return (
    <div
      className="absolute right-0 top-0 z-50 h-full w-80 border-l shadow-xl overflow-y-auto transition-transform duration-300 ease-out"
      style={{
        background: 'var(--card)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 p-4 border-b" style={{ borderColor: 'var(--border)' }}>
        <Icon className="h-5 w-5 shrink-0" style={{ color }} />
        <h3 className="text-sm font-semibold text-foreground truncate flex-1">
          {node.name}
        </h3>
        <button
          onClick={onClose}
          className="h-6 w-6 shrink-0 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Entity type + depth */}
      <div className="px-4 pt-3 pb-2 flex items-center gap-2">
        <span
          className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium"
          style={{
            background: `color-mix(in oklch, ${color} 10%, transparent)`,
            color,
          }}
        >
          {node.entityType}
        </span>
        <span className="text-[10px] text-muted-foreground">
          Depth {node.depth}
        </span>
      </div>

      {/* Properties */}
      {propEntries.length > 0 && (
        <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <p className="section-label mb-2">Properties</p>
          <dl className="space-y-1.5">
            {propEntries.map(([key, value]) => (
              <div key={key} className="text-xs">
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="text-foreground/80 break-words mt-0.5">
                  {String(value ?? '')}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Connections */}
      <div className="px-4 py-3">
        <p className="section-label mb-2">
          Connections ({connections.length})
        </p>
        {connections.length === 0 ? (
          <p className="text-xs text-muted-foreground">No connections</p>
        ) : (
          <div className="space-y-0.5">
            {connections.map((conn) => {
              const ConnIcon = ENTITY_ICONS[conn.node.entityType]
              const connColor = ENTITY_COLORS[conn.node.entityType]
              const DirIcon = conn.direction === 'outgoing' ? ArrowRight : ArrowLeft

              return (
                <button
                  key={`${conn.node.id}-${conn.edgeType}-${conn.direction}`}
                  onClick={() => handleConnectionClick(conn.node.id)}
                  className="w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-muted/30 transition-colors text-left group"
                >
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: connColor }}
                  />
                  <span className="text-foreground/80 truncate flex-1 group-hover:text-foreground transition-colors">
                    {conn.node.name}
                  </span>
                  <span
                    className="shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium"
                    style={{
                      background: 'var(--muted)',
                      color: 'var(--muted-foreground)',
                    }}
                  >
                    {conn.edgeType}
                  </span>
                  <DirIcon className="h-3 w-3 shrink-0 text-muted-foreground" />
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
